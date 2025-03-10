// Copyright (c) 2025, info@byoosi.com and contributors
// For license information, please see license.txt

frappe.query_reports["Patient Billing and Revenues"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "patient",
			"label": __("Patient"),
			"fieldtype": "Link",
			"options": "Patient"
		},
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname": "cost_center",
			"label": __("Cost Centre"),
			"fieldtype": "Link",
			"options": "Cost Center"
		},
		{
			"fieldname": "account",
			"label": __("Income Account"),
			"fieldtype": "Link",
			"options": "Account",
			"get_query": function() {
				return {
					"filters": {
						"is_group": 0,
						"account_type": "Income Account"
					}
				}
			}
		},
		{
			"fieldname": "mode_of_payment",
			"label": __("Mode of Payment"),
			"fieldtype": "Link",
			"options": "Mode of Payment"
		},
		{
			"fieldname": "status",
			"label": __("Invoice Status"),
			"fieldtype": "Select",
			"options": "\nDraft\nReturn\nCredit Note Issued\nSubmitted\nPaid\nUnpaid\nOverdue\nCancelled"
		}
	]
};
