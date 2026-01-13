import frappe

@frappe.whitelist()
def after_migrate():
    validate_stock_entry_types()


def validate_stock_entry_types():
    _validate_stock_entry_type("Feeding Entry", "Material Issue")
    _validate_stock_entry_type("Treatment Entry", "Material Issue")


def _validate_stock_entry_type(entry_type, purpose):
    # Ensure a Stock Entry Type exists, create it if not.
    if not frappe.db.exists("Stock Entry Type", entry_type):
        doc = frappe.get_doc({
            "doctype": "Stock Entry Type",
            "name": entry_type,
            "purpose": purpose,
            "is_standard": 0
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.log_error(f"Created Stock Entry Type: {entry_type}", "Stock Entry Type Creation")
