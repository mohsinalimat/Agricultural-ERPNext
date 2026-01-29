import frappe

from frappe import _

from frappe.utils import get_link_to_form

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
    purchase_account = settings.get("sold_credit_account")
    feeding_account  = settings.get("sold_credit_account_feeding")
    wages_account  = settings.get("sold_credit_account_wages_and_salaries")
    maintenance_account  = settings.get("sold_credit_account_maintenance")

    def create_journal_entry(
        animal_record, 
        total_cost,
        purchase_cost,
        feeding_cost,
        wages_cost,
        maintenance_cost
    ):
        purchase_cost = round(purchase_cost or 0, 2)
        feeding_cost = round(feeding_cost or 0, 2)
        wages_cost = round(wages_cost or 0, 2)
        maintenance_cost = round(maintenance_cost or 0, 2)

        total_cost = round(
            purchase_cost
            + feeding_cost
            + wages_cost
            + maintenance_cost
        , 2)

        if total_cost == 0:
            return

        if (
            (total_cost != 0 and not debit_account) or
            (purchase_cost != 0 and not purchase_account) or
            (feeding_cost != 0 and not feeding_account) or
            (wages_cost != 0 and not wages_account) or
            (maintenance_cost != 0 and not maintenance_account)    
        ):
            frappe.throw("Please add selling accounts in agriculture setting.")


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
                "debit": abs(total_cost) if total_cost > 0 else 0,
                "debit_in_account_currency": abs(total_cost) if total_cost > 0 else 0,
                "credit": abs(total_cost) if total_cost < 0 else 0,
                "credit_in_account_currency": abs(total_cost) if total_cost < 0 else 0,
            },
        )

        if purchase_cost != 0:
            je.append(
                "accounts",
                {
                    "account": purchase_account,
                    "debit": 0,
                    "debit_in_account_currency": 0,
                    "credit": purchase_cost,
                    "credit_in_account_currency": purchase_cost,
                },
            )

        if feeding_cost != 0:
            je.append(
                "accounts",
                {
                    "account": feeding_account,
                    "debit": 0,
                    "debit_in_account_currency": 0,
                    "credit": feeding_cost,
                    "credit_in_account_currency": feeding_cost,
                },
            )

        if wages_cost != 0:
            je.append(
                "accounts",
                {
                    "account": wages_account,
                    "debit": abs(wages_cost) if wages_cost < 0 else 0,
                    "debit_in_account_currency": abs(wages_cost) if wages_cost < 0 else 0,
                    "credit": abs(wages_cost) if wages_cost > 0 else 0,
                    "credit_in_account_currency": abs(wages_cost) if wages_cost > 0 else 0,
                },
            )
        
        if maintenance_cost != 0:
            je.append(
                "accounts",
                {
                    "account": maintenance_account,
                    "debit": abs(maintenance_cost) if maintenance_cost < 0 else 0,
                    "debit_in_account_currency": abs(maintenance_cost) if maintenance_cost < 0 else 0,
                    "credit": abs(maintenance_cost) if maintenance_cost > 0 else 0,
                    "credit_in_account_currency": abs(maintenance_cost) if maintenance_cost > 0 else 0,
                },
            )

        # Load settings for debit/credit accounts
        settings = frappe.get_single("Agriculture Setting")
        
        je.insert()
        if settings.get('submit_sold_journal_entry'):
            je.submit()

        return je.name

    for row in doc.items:
        animal_record = row.get("custom_animal_record")
        if not animal_record:
            continue

        animal_doc = frappe.get_doc('Animal Record', animal_record)
        if animal_doc.status != 'Active':
            animal_link = get_link_to_form("Animal Record", animal_record)
            frappe.throw(_(
                "Can't Submit Sales Invoice, Animal Record {0} Isn't Active."
            ).format(animal_link))

    # Loop rows
    for row in doc.items:
        if not row.get("custom_animal_record"):
            continue

        # Get Total Cost From Animal Record
        total_cost = frappe.get_value("Animal Record", row.custom_animal_record, 'total_cost') or 0
        purchase_cost = frappe.get_value("Animal Record", row.custom_animal_record, 'purchase_price') or 0
        feeding_cost = frappe.get_value("Animal Record", row.custom_animal_record, 'cost_to_date') or 0
        treatment_cost = frappe.get_value("Animal Record", row.custom_animal_record, 'treatment_cost_to_date') or 0
        wages_cost = frappe.get_value("Animal Record", row.custom_animal_record, 'wages_and_salaries_cost') or 0
        maintenance_cost = frappe.get_value("Animal Record", row.custom_animal_record, 'maintenance_cost') or 0

        if not total_cost:
            continue

        je_name = create_journal_entry(
            row.custom_animal_record, 
            total_cost, 
            purchase_cost,
            feeding_cost + treatment_cost,
            wages_cost,
            maintenance_cost
        )
        
        frappe.db.set_value("Sales Invoice Item", row.name, "custom_journal_entry", je_name)


def cancel_journal_entry_for_animal_records(doc):
    for row in doc.items:
        if row.custom_journal_entry and frappe.db.exists("Journal Entry", row.custom_journal_entry):
            je = frappe.get_doc("Journal Entry", row.custom_journal_entry)
            if je.docstatus == 1:
                je.cancel()

        if row.custom_animal_record:
            frappe.db.set_value("Animal Record", row.custom_animal_record, "status", "Active")
        