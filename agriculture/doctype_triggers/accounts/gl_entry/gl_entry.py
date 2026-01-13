import frappe

from frappe import _

from agriculture.agriculture.doctype.animal_record.animal_record import calculate_accounting_cost

@frappe.whitelist()
def before_insert(doc, method=None):
    pass

@frappe.whitelist()
def after_insert(doc, method=None):
    if doc.herd_group:
        calculate_accounting_cost(doc.herd_group)

@frappe.whitelist()
def onload(doc, method=None):
    pass
@frappe.whitelist()
def before_validate(doc, method=None):
    pass
@frappe.whitelist()
def validate(doc, method=None):
    pass
@frappe.whitelist()
def on_submit(doc, method=None):
    pass
@frappe.whitelist()
def on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def before_save(doc, method=None):
    pass
@frappe.whitelist()
def before_cancel(doc, method=None):
    pass

@frappe.whitelist()
def on_update(doc, method=None):
    if doc.herd_group:
        calculate_accounting_cost(doc.herd_group)