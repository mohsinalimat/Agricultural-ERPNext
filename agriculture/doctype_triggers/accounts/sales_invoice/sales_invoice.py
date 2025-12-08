import frappe

from frappe import _

@frappe.whitelist()
def before_insert(doc, method=None):
    pass
@frappe.whitelist()
def after_insert(doc, method=None):
    pass
@frappe.whitelist()
def onload(doc, method=None):
    pass

@frappe.whitelist()
def before_validate(doc, method=None):
    #  Chech if there mandatory fields not entered
    validate_required_fields(doc)

@frappe.whitelist()
def validate(doc, method=None):
    pass

@frappe.whitelist()
def on_submit(doc, method=None):
    # Create journal Entry For Each Animal Record based on total cost
    create_journal_entry_for_animal_records(doc)

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
    cancel_journal_entry_for_animal_records(doc)

@frappe.whitelist()
def on_update(doc, method=None):
    pass

def validate_required_fields(doc):
    # Check all Animal Records for Animal Items
    for row in doc.items:
        if not row.get('item_code'):
            continue

        is_animal = frappe.get_value("Item", row.item_code, 'custom_is_animal')

        if is_animal and not row.get('custom_animal_record'):
            frappe.throw(f"Row {row.idx}: Animal Record Is Required for Item {row.item_code}")


def create_journal_entry_for_animal_records(doc):
    # Get accounts from Agriculture Settings
    settings = frappe.get_single("Agriculture Setting")

    debit_account  = settings.get("sold_debit_account")
    credit_account = settings.get("sold_credit_account")

    def create_journal_entry(animal_record, total_cost):
        # Create Journal Entry
        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "company": doc.company,
            "custom_animal_state": "Sold",
            "custom_animal_record": animal_record,
            "posting_date": doc.posting_date or frappe.utils.nowdate(),
            "user_remark": _("Auto-created for Animal Record: {0}").format(row.item_code),
        })

        je.append(
            "accounts",
            {
                "account": debit_account,
                "debit": total_cost,
                "debit_in_account_currency": total_cost,
                "credit": 0,
                "credit_in_account_currency": 0,
            },
        )

        je.append(
            "accounts",
            {
                "account": credit_account,
                "debit": 0,
                "debit_in_account_currency": 0,
                "credit": total_cost,
                "credit_in_account_currency": total_cost,
            },
        )

        je.insert()
        je.submit()
        
        # Change Animal Record Status As Sold
        frappe.set_value("Animal Record", animal_record, 'status', "Sold")

        return je.name

    # Loop rows
    for row in doc.items:
        # Get Total Cost From Animal Record
        total_cost = frappe.get_value("Animal Record", row.custom_animal_record, 'total_cost') or 0

        if not row.get("custom_animal_record") or not total_cost:
            continue

        if not debit_account or not credit_account:
            frappe.throw(
                _("Sold Debit Account and Sold Credit Account are Required in Agriculture Setting to Create Journal Entry.")
            )

        je_name = create_journal_entry(row.custom_animal_record, total_cost)
        
        frappe.db.set_value("Sales Invoice Item", row.name, "custom_journal_entry", je_name)

def cancel_journal_entry_for_animal_records(doc):
    for row in doc.items:
        if row.custom_journal_entry:
            je = frappe.get_doc("Journal Entry", row.custom_journal_entry)
            if je.docstatus == 1:
                je.cancel()

        if row.custom_animal_record:
            frappe.db.set_value("Animal Record", row.custom_animal_record, "status", "Active")
        