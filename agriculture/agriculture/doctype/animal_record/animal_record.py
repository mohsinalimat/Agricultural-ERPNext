# Copyright (c) 2025, Ismail Akram and contributors
# For license information, please see license.txt

import frappe

from frappe.model.document import Document

from frappe import _
from frappe.model.mapper import get_mapped_doc

from agriculture.agriculture.doctype.herd_group.herd_group import update_herd_data

class AnimalRecord(Document):
    def after_insert(self):
        # Update Herd Group data after inserting Animal Record
        update_herd_data(self.herd)


    def before_validate(self):
        # Calculte total fields 
        calculate_total(self)

        # Update Herd Group data after inserting Animal Record
        update_herd_data(self.herd)


    def after_delete(self):
        # Update Herd Group data after deleting Animal Record
        update_herd_data(self.herd)


def calculate_total(doc):
    doc.current_fair_value = (doc.current_weight_kg or 0) * (doc.carrying_value or 0)
    doc.total_cost = (doc.purchase_price or 0) + (doc.cost_to_date or 0)


@frappe.whitelist()
def create_sales_invoice(source_name, target_doc=None):
    animal_record = frappe.get_doc("Animal Record", source_name)

    target_doc = get_mapped_doc(
        "Animal Record",
        source_name,
        {
            "Animal Record": {
                "doctype": "Sales Invoice",
            }
        },
        target_doc,
    )

    target_doc.due_date = frappe.utils.nowdate()

    target_doc.append("items", {
        "item_code": animal_record.livestock_master,
        "item_name": frappe.get_value("Item", animal_record.livestock_master, "item_name"),
        "custom_animal_record": animal_record.name,
        "uom": frappe.get_value("Item", animal_record.livestock_master, "stock_uom"),
        "qty": 1,
        "rate": animal_record.current_fair_value,
        "amount": animal_record.current_fair_value,
    })

    return target_doc

# Create a Journal Entry for Birth or Dead Animal and link it to the Animal Record.
@frappe.whitelist()
def create_journal_entry(animal_record, entry_type, amount=0):
    if not animal_record or not entry_type:
        frappe.throw(_("Animal Record and Entry Type are required."))

    # Load animal document
    animal_doc = frappe.get_doc("Animal Record", animal_record)

    # Load settings for debit/credit accounts
    settings = frappe.get_single("Agriculture Setting")

    debit_account = ""
    credit_account = ""

    # Determine accounts and amount based on entry type
    if entry_type == "Birth":
        debit_account = settings.get("birth_debit_account")
        credit_account = settings.get("birth_credit_account")
        amount = animal_doc.get("current_fair_value", 0) or 0
        submit_doc = settings.get('submit_birth_journal_entry')

    elif entry_type == "Dead":
        debit_account = settings.get("dead_debit_account")
        credit_account = settings.get("dead_credit_account")
        amount = animal_doc.get("total_cost", 0) or 0
        submit_doc = settings.get('submit_dead_journal_entry')

    else:
        return

    # Validate required accounts
    if not debit_account or not credit_account:
        frappe.throw(
            _("{0} Debit Account and {0} Credit Account must be set in Agriculture Setting.")
            .format(entry_type)
        )

    # Validate amount
    if amount <= 0:
        frappe.throw(_("Amount calculated for the Journal Entry is zero."))

    # Get default company
    default_company = (
        frappe.defaults.get_user_default("company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
        or frappe.db.get_value("Company", {}, "name")
    )

    # Create Journal Entry document
    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "company": default_company,
        "posting_date": frappe.utils.nowdate(),
        "custom_animal_state": entry_type,
        "custom_animal_record": animal_record,
        "user_remark": _("{0} for Animal Record {1}".format(entry_type, animal_record)),
    })

    # Debit Line
    je.append("accounts", {
        "account": debit_account,
        "debit": amount,
        "debit_in_account_currency": amount,
    })

    # Credit Line
    je.append("accounts", {
        "account": credit_account,
        "credit": amount,
        "credit_in_account_currency": amount,
    })

    # Save + Submit JE
    je.insert()
    if submit_doc:
        je.submit()

    # Update animal record
    if entry_type == "Birth":
        frappe.set_value("Animal Record", animal_record, "birth_journal_entry", je.name)

    elif entry_type == "Dead":
        frappe.set_value("Animal Record", animal_record, "dead_journal_entry", je.name)
        frappe.set_value("Animal Record", animal_record, "status", "Dead")

    # Success message with link
    frappe.msgprint(
        _(
            "Journal Entry <a href='/app/journal-entry/{0}' target='_blank'><b>{0}</b></a> has been created successfully."
        ).format(je.name),
    )

    return je.name