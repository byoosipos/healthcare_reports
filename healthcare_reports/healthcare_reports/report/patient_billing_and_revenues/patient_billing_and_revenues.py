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
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 120},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 120},
		{"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 130},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
		{"label": _("Income Account"), "fieldname": "income_account", "fieldtype": "Link", "options": "Account", "width": 150},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Invoiced Amount"), "fieldname": "invoiced_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Amount Paid"), "fieldname": "amount_paid", "fieldtype": "Currency", "width": 120},
		{"label": _("Outstanding Amount"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120}
	]

def get_data(filters):
	conditions = get_conditions(filters)
	
	data = frappe.db.sql("""
		SELECT 
			p.name as patient,
			p.patient_name,
			p.customer,
			si.customer_name,
			si.posting_date,
			'Sales Invoice' as voucher_type,
			si.name as voucher_no,
			sii.item_code,
			sii.item_name,
			sii.income_account,
			sii.qty,
			sii.rate,
			sii.amount,
			IFNULL((
				SELECT SUM(debit)
				FROM `tabGL Entry` gle_debit
				WHERE gle_debit.voucher_no = si.name
				AND gle_debit.docstatus = 1
				AND gle_debit.is_cancelled = 0
			), 0) as invoiced_amount,
			IFNULL((
				SELECT SUM(credit)
				FROM `tabGL Entry` gle_credit
				WHERE gle_credit.against_voucher = si.name
				AND gle_credit.docstatus = 1
				AND gle_credit.is_cancelled = 0
			), 0) as amount_paid,
			IFNULL((
				SELECT SUM(debit)
				FROM `tabGL Entry` gle_debit
				WHERE gle_debit.voucher_no = si.name
				AND gle_debit.docstatus = 1
				AND gle_debit.is_cancelled = 0
			), 0) - IFNULL((
				SELECT SUM(credit)
				FROM `tabGL Entry` gle_credit
				WHERE gle_credit.against_voucher = si.name
				AND gle_credit.docstatus = 1
				AND gle_credit.is_cancelled = 0
			), 0) as outstanding_amount
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
	
	return data

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
