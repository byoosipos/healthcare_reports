# Copyright (c) 2025, info@byoosi.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{"label": _("Patient ID"), "fieldname": "patient", "fieldtype": "Link", "options": "Patient", "width": 120},
		{"label": _("Patient Name"), "fieldname": "patient_name", "fieldtype": "Data", "width": 150},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 120},
		{"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 130},
		{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Dynamic Link", "options": "reference_type", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 180},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Amount Paid"), "fieldname": "amount_paid", "fieldtype": "Currency", "width": 120},
		{"label": _("Outstanding Amount"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120}
	]

def get_data(filters):
	conditions = get_conditions(filters)
	invoice_conditions = get_invoice_conditions(filters)
	
	# Get Sales Invoice data (items and income accounts)
	sales_invoice_data = frappe.db.sql("""
		SELECT 
			p.name as patient,
			p.patient_name,
			si.customer_name,
			si.posting_date,
			'Sales Invoice' as voucher_type,
			si.name as voucher_no,
			NULL as reference_type,
			NULL as reference,
			sii.item_name,
			sii.income_account as account,
			sii.qty,
			sii.rate,
			sii.amount,
			0 as amount_paid,
			sii.amount as outstanding_amount
		FROM
			`tabSales Invoice` si
		INNER JOIN
			`tabSales Invoice Item` sii ON si.name = sii.parent
		INNER JOIN
			`tabPatient` p ON si.patient = p.name
		WHERE
			si.docstatus = 1
			{conditions}
		ORDER BY
			si.posting_date DESC, si.name, sii.idx
	""".format(conditions=conditions), filters, as_dict=1)
	
	# Get Payment Entry data
	payment_data = frappe.db.sql("""
		SELECT 
			p.name as patient,
			p.patient_name,
			c.customer_name,
			pe.posting_date,
			'Payment Entry' as voucher_type,
			pe.name as voucher_no,
			'Sales Invoice' as reference_type,
			per.reference_name as reference,
			'Payment' as item_name,
			pe.paid_to as account,
			1 as qty,
			per.allocated_amount as rate,
			per.allocated_amount as amount,
			per.allocated_amount as amount_paid,
			0 as outstanding_amount
		FROM
			`tabPayment Entry` pe
		INNER JOIN
			`tabPayment Entry Reference` per ON pe.name = per.parent
		INNER JOIN
			`tabSales Invoice` si ON per.reference_name = si.name
		INNER JOIN
			`tabPatient` p ON si.patient = p.name
		INNER JOIN
			`tabCustomer` c ON si.customer = c.name
		WHERE
			pe.docstatus = 1
			AND pe.payment_type = 'Receive'
			{conditions}
		ORDER BY
			pe.posting_date DESC, pe.name
	""".format(conditions=get_payment_conditions(filters)), filters, as_dict=1)
	
	# Combine data
	combined_data = sales_invoice_data + payment_data
	
	# Sort the combined data by posting_date
	combined_data.sort(key=lambda x: x.posting_date, reverse=True)
	
	# Update the outstanding amounts on Sales Invoice rows based on related payments
	invoice_payments = {}
	invoice_total_amounts = {}
	
	# Collect all payments by invoice reference
	for row in payment_data:
		if row.reference not in invoice_payments:
			invoice_payments[row.reference] = 0
		invoice_payments[row.reference] += row.amount_paid
	
	# Get the total amount of each invoice first
	for row in sales_invoice_data:
		if row.voucher_no not in invoice_total_amounts:
			invoice_total_amounts[row.voucher_no] = 0
		invoice_total_amounts[row.voucher_no] += row.amount
	
	# Now update the outstanding amounts based on proportional payments
	for row in combined_data:
		if row.voucher_type == 'Sales Invoice':
			if row.voucher_no in invoice_payments and invoice_total_amounts[row.voucher_no] > 0:
				# Calculate what portion of the total invoice this line represents
				line_proportion = row.amount / invoice_total_amounts[row.voucher_no]
				# Apply that proportion of the total payment to this line's outstanding amount
				proportional_payment = invoice_payments.get(row.voucher_no, 0) * line_proportion
				row.outstanding_amount = max(0, row.amount - proportional_payment)
	
	return combined_data

def get_payment_conditions(filters):
	conditions = []
	
	if filters.get("from_date"):
		conditions.append("pe.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("pe.posting_date <= %(to_date)s")
	if filters.get("patient"):
		conditions.append("p.name = %(patient)s")
	if filters.get("account"):
		conditions.append("pe.paid_to = %(account)s")
	if filters.get("mode_of_payment"):
		conditions.append("pe.mode_of_payment = %(mode_of_payment)s")
	
	return " AND " + " AND ".join(conditions) if conditions else ""

def get_invoice_conditions(filters):
	conditions = []
	
	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
	if filters.get("patient"):
		conditions.append("si.patient = %(patient)s")
	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")
	if filters.get("status"):
		conditions.append("si.status = %(status)s")
	
	# For account filter, we need to handle it differently for the invoice query
	if filters.get("account"):
		conditions.append("""EXISTS (
			SELECT 1 FROM `tabSales Invoice Item` 
			WHERE parent = si.name 
			AND income_account = %(account)s
		)""")
	
	if filters.get("mode_of_payment"):
		conditions.append("""EXISTS (
			SELECT 1 FROM `tabGL Entry` gle_payment
			WHERE gle_payment.against_voucher = si.name
			AND gle_payment.voucher_type = 'Payment Entry'
			AND EXISTS (
				SELECT 1 FROM `tabPayment Entry` pe
				WHERE pe.name = gle_payment.voucher_no
				AND pe.mode_of_payment = %(mode_of_payment)s
			)
		)""")
	
	return " AND " + " AND ".join(conditions) if conditions else ""

def get_conditions(filters):
	conditions = []
	
	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
	if filters.get("patient"):
		conditions.append("p.name = %(patient)s")
	if filters.get("customer"):
		conditions.append("p.customer = %(customer)s")
	if filters.get("cost_center"):
		conditions.append("sii.cost_center = %(cost_center)s")
	if filters.get("account"):
		conditions.append("sii.income_account = %(account)s")
	if filters.get("mode_of_payment"):
		conditions.append("""EXISTS (
			SELECT 1 FROM `tabGL Entry` gle_payment
			WHERE gle_payment.against_voucher = si.name
			AND gle_payment.voucher_type = 'Payment Entry'
			AND EXISTS (
				SELECT 1 FROM `tabPayment Entry` pe
				WHERE pe.name = gle_payment.voucher_no
				AND pe.mode_of_payment = %(mode_of_payment)s
			)
		)""")
	if filters.get("status"):
		conditions.append("si.status = %(status)s")
	
	return " AND " + " AND ".join(conditions) if conditions else ""
