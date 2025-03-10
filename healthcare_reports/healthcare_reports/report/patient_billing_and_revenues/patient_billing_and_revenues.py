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
		{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Data", "width": 150},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 180},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120}
	]

def get_data(filters):
	data = []
	
	# Get Sales Invoice data (items and income accounts)
	invoice_conditions = get_invoice_conditions(filters)
	sales_invoice_data = frappe.db.sql("""
		SELECT 
			p.name as patient,
			p.patient_name,
			si.customer_name,
			si.posting_date,
			'Sales Invoice' as voucher_type,
			si.name as voucher_no,
			'' as reference,
			sii.item_name,
			sii.income_account as account,
			sii.qty,
			sii.rate,
			sii.amount
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
	""".format(conditions=invoice_conditions), filters, as_dict=1)
	
	data.extend(sales_invoice_data)
	
	# Get Payment Entry data
	payment_conditions = get_payment_conditions(filters)
	payment_data = frappe.db.sql("""
		SELECT 
			p.name as patient,
			p.patient_name,
			c.customer_name,
			pe.posting_date,
			'Payment Entry' as voucher_type,
			pe.name as voucher_no,
			per.reference_name as reference,
			'Payment' as item_name,
			pe.paid_to as account,
			1 as qty,
			per.allocated_amount as rate,
			per.allocated_amount as amount
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
	""".format(conditions=payment_conditions), filters, as_dict=1)
	
	data.extend(payment_data)
	
	# Get Journal Entry data affecting patient invoices
	journal_conditions = get_journal_conditions(filters)
	journal_data = frappe.db.sql("""
		SELECT 
			p.name as patient,
			p.patient_name,
			c.customer_name,
			je.posting_date,
			'Journal Entry' as voucher_type,
			je.name as voucher_no,
			jea.reference_name as reference,
			CONCAT(je.title, ' - ', jea.account) as item_name,
			jea.account as account,
			1 as qty,
			jea.credit as rate,
			jea.credit as amount
		FROM
			`tabJournal Entry` je
		INNER JOIN
			`tabJournal Entry Account` jea ON je.name = jea.parent
		INNER JOIN
			`tabSales Invoice` si ON jea.reference_name = si.name
		INNER JOIN
			`tabPatient` p ON si.patient = p.name
		INNER JOIN
			`tabCustomer` c ON si.customer = c.name
		WHERE
			je.docstatus = 1
			AND jea.reference_type = 'Sales Invoice'
			AND jea.credit > 0
			{conditions}
		
		UNION ALL
		
		SELECT 
			p.name as patient,
			p.patient_name,
			c.customer_name,
			je.posting_date,
			'Journal Entry' as voucher_type,
			je.name as voucher_no,
			jea.reference_name as reference,
			CONCAT(je.title, ' - ', jea.account) as item_name,
			jea.account as account,
			1 as qty,
			jea.debit * -1 as rate,
			jea.debit * -1 as amount
		FROM
			`tabJournal Entry` je
		INNER JOIN
			`tabJournal Entry Account` jea ON je.name = jea.parent
		INNER JOIN
			`tabSales Invoice` si ON jea.reference_name = si.name
		INNER JOIN
			`tabPatient` p ON si.patient = p.name
		INNER JOIN
			`tabCustomer` c ON si.customer = c.name
		WHERE
			je.docstatus = 1
			AND jea.reference_type = 'Sales Invoice'
			AND jea.debit > 0
			{conditions}
	""".format(conditions=journal_conditions), filters, as_dict=1)
	
	data.extend(journal_data)
	
	# Sort the combined data by posting_date
	data.sort(key=lambda x: (x.posting_date, x.voucher_type, x.voucher_no), reverse=True)
	
	return data

def get_journal_conditions(filters):
	conditions = []
	
	if filters.get("from_date"):
		conditions.append("je.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("je.posting_date <= %(to_date)s")
	if filters.get("patient"):
		conditions.append("p.name = %(patient)s")
	if filters.get("account"):
		conditions.append("jea.account = %(account)s")
	
	return " AND " + " AND ".join(conditions) if conditions else ""

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
