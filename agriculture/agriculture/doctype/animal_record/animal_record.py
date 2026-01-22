# Copyright (c) 2025, Ismail Akram and contributors
# For license information, please see license.txt

import frappe
import json
import os
import io

from frappe import _
from base64 import b64encode

from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from pyqrcode import create as qr_create

from agriculture.agriculture.doctype.herd_group.herd_group import update_herd_data

class AnimalRecord(Document):
    def before_insert(self):
        # Throw Error If There are Missing Fields in the doc
        validate_missing_fields(self)

        # Set Missing Fields in the doc
        set_missing_fields(self)


    def after_insert(self):
        # Update Herd Group data after inserting Animal Record
        update_herd_data(self.herd)

        if self.animal_source == 'Internal Birth':
            create_journal_entry(self.name, 'Birth', self.purchase_price)


    def before_validate(self):
        # Throw Error If There are Missing Fields in the doc
        validate_missing_fields(self)
        
        # Validate Missing Fields in the doc
        set_missing_fields(self)

        # Calculte total fields 
        calculate_total(self)

        # Update Herd Group data after inserting Animal Record
        update_herd_data(self.herd)

    def on_update(self):
        # Validate Missing Fields in the doc
        set_missing_fields(self)

    def after_delete(self):
        # Update Herd Group data after deleting Animal Record
        update_herd_data(self.herd)


# Throw Error If There are Missing Fields in the doc
def validate_missing_fields(self):
    if self.animal_source == 'Internal Birth' and not self.purchase_price:
        frappe.throw("Missing Field: 'Purchase Price'")


# Validate Missing Fields in the doc
def set_missing_fields(self):
    self.breed = frappe.get_value("Item", self.livestock_master, "custom_breed")

    self.current_weight_kg = self.current_weight_kg or 1

    if self.animal_source == 'Internal Birth' and self.mother_tag:
        update_number_of_children(self.mother_tag)


def calculate_total(doc):
    doc.current_fair_value = (doc.current_weight_kg or 0) * (doc.carrying_value or 0)
    doc.total_cost = (
        (doc.purchase_price or 0) + (doc.cost_to_date or 0) + (doc.treatment_cost_to_date or 0) + 
        (doc.wages_and_salaries_cost or 0) + (doc.maintenance_cost) 
    )


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


@frappe.whitelist()
def bulk_create_sales_invoice(animal_records):
    if isinstance(animal_records, str):
        animal_records = frappe.parse_json(animal_records)

    if not animal_records:
        frappe.throw(_("No Animal Records selected."))

    # Use first record only to create base mapped doc
    first_animal = frappe.get_doc("Animal Record", animal_records[0])

    target_doc = get_mapped_doc(
        "Animal Record",
        first_animal.name,
        {
            "Animal Record": {
                "doctype": "Sales Invoice",
            }
        },
        None,
    )

    target_doc.due_date = frappe.utils.nowdate()

    for animal_name in animal_records:
        animal = frappe.get_doc("Animal Record", animal_name)

        if animal.status != 'Active':
            continue

        if not animal.livestock_master:
            continue

        target_doc.append("items", {
            "item_code": animal.livestock_master,
            "item_name": frappe.get_value("Item", animal.livestock_master, "item_name"),
            "custom_animal_record": animal.name,
            "uom": frappe.get_value("Item", animal.livestock_master, "stock_uom"),
            "qty": 1,
            "rate": animal.current_fair_value,
            "amount": animal.current_fair_value,
        })

    return target_doc


# Create a Journal Entry for Birth or Dead Animal and link it to the Animal Record.
@frappe.whitelist()
def create_journal_entry(animal_record, entry_type, amount=0, no_link=0):
    if not animal_record or not entry_type:
        frappe.throw(_("Animal Record and Entry Type are required."))

    # Load animal document
    animal_doc = frappe.get_doc("Animal Record", animal_record)

    # Load settings for debit/credit accounts
    settings = frappe.get_single("Agriculture Setting")

    debit_account = ""
    credit_account = ""

    # Determine accounts and amount based on entry type
    if entry_type in ["Birth", "Fair Value"]:
        amount_field = "current_fair_value" if entry_type == "Birth" else "purchase_price"

        debit_account = settings.get("birth_debit_account")
        credit_account = settings.get("birth_credit_account")
        amount = amount or (animal_doc.get(amount_field, 0) or 0)
        submit_doc = settings.get('submit_birth_journal_entry')
    elif entry_type == "Dead":
        debit_account = settings.get("dead_debit_account")
        credit_account = settings.get("dead_credit_account")
        amount = amount or animal_doc.get("current_fair_value", 0) or 0
        submit_doc = settings.get('submit_dead_journal_entry')
    else:
        return

    # Validate required accounts
    if not debit_account or not credit_account:
        frappe.throw(
            _("{0} Debit Account and {0} Credit Account must be set in Agriculture Setting.")
            .format(entry_type)
        )

    if amount < 0:
        amount *= -1
        debit_account, credit_account = credit_account, debit_account

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

    # Success message with link
    frappe.msgprint(
        _(
            "Journal Entry <a href='/app/journal-entry/{0}' target='_blank'><b>{0}</b></a> has been created successfully for animal record <a href='/app/animal-record/{1}' target='_blank'><b>{1}</b></a>."
        ).format(je.name, animal_record),
    )

    return je.name


@frappe.whitelist()
def update_fair_value(animal_record, data):
    # Return immediately if no animal record is provided
    if not animal_record:
        return
    
    # If data is a string, parse it
    if isinstance(data, str):
        data = json.loads(data)

    # Fetch the Animal Record document
    animal_doc = frappe.get_doc("Animal Record", animal_record)

    if animal_doc.status != 'Active':
        return
    
    # Extract values from data
    current_weight = data.get('current_weight', 0) or 0
    carrying_value = data.get('carrying_value', 0) or 0
    new_fair_value = current_weight * carrying_value
    valuation_date = data.get('valuation_date')
    diff_amount = new_fair_value - (animal_doc.current_fair_value or 0)

    # Append the previous values to the child table 'fair_value_details' for history
    animal_doc.append("fair_value_details", {
        "current_weight_kg": animal_doc.current_weight_kg,
        "carrying_value": animal_doc.carrying_value,
        "fair_value": animal_doc.current_fair_value,
        "valuation_date": animal_doc.last_valuation_date,
    })

    # Update the main fields of the animal record
    animal_doc.current_weight_kg = current_weight
    animal_doc.carrying_value = carrying_value
    animal_doc.current_fair_value = new_fair_value
    animal_doc.last_valuation_date = valuation_date

    # Save the document
    animal_doc.save(ignore_permissions=True)
    
    # Create a journal entry for the difference in fair value
    if diff_amount != 0:
        create_journal_entry(animal_record, "Fair Value", diff_amount, 1)


@frappe.whitelist()
def bulk_update_fair_value(animal_records, data):
    if not animal_records:
        return {"updated": 0, "failed": []}

    if isinstance(animal_records, str):
        animal_records = json.loads(animal_records)

    if isinstance(data, str):
        data = json.loads(data)

    updated = 0
    errors = []
    skipped = []

    for animal_record in animal_records:
        try:
            # Only allow bulk updates for active records to match form button behavior.
            status = frappe.db.get_value("Animal Record", animal_record, "status")
            if status != "Active":
                skipped.append(animal_record)
                continue

            update_fair_value(animal_record, data)
            updated += 1
        except Exception:
            # Capture per-record failures so a single error doesn't stop the batch.
            errors.append(
                {
                    "animal_record": animal_record,
                    "error": frappe.get_traceback(),
                }
            )

    if errors:
        # Log full tracebacks for troubleshooting without blocking the UI response.
        frappe.log_error(
            title="Bulk Update Fair Value Errors",
            message=json.dumps(errors),
        )

    failed = [error.get("animal_record") for error in errors]
    return {"updated": updated, "failed": failed, "skipped": skipped}


# Create Qr Code Includes the data of the animal Record
@frappe.whitelist()
def create_qr_code(animal_record):
    doc = frappe.get_doc('Animal Record', animal_record)

    # Build a readable, line-separated payload instead of JSON
    qr_lines = []
    qr_fields = [
        ("Name", "name"),
        ("Sex", "sex"),
        ("Herd", "herd"),
        ("Status", "status"),
        ("Livestock Master", "livestock_master"),
        ("Animal Source", "animal_source"),
        ("Breed", "breed"),
    ]

    if doc.animal_source == "Internal Birth":
        qr_fields.append(("Mother Tag", "mother_tag"))
        
    if doc.animal_source == "Purchased":
        qr_fields.extend([
            ("Purchase Date", "purchase_date"),
            ("Purchase Price", "purchase_price")
        ])
    
    qr_fields.extend([
        ("Current Fair Value", "current_fair_value"),
        ("Total Cost", "total_cost"),
        ("Last Valuation Date", "last_valuation_date"),
    ])

    for label, fieldname in qr_fields:
        value = doc.name if fieldname == "name" else (doc.get_formatted(fieldname) or doc.get(fieldname))

        if value in (None, "", 0):
            continue
        
        qr_lines.append(f"{label}: {value or ''}")

    qr_payload = "\n".join(qr_lines)

    # Generate QR image
    qr_image = io.BytesIO()
    qr_create(qr_payload, error="L", encoding="utf-8").png(
        qr_image,
        scale=3,
        quiet_zone=1
    )

    # Save The Qr File
    filename = f"AnimalRecord-{doc.name}.png".replace(os.path.sep, "__")
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": filename,
            "is_private": 0,
            "content": qr_image.getvalue(),
            "attached_to_doctype": doc.doctype,
            "attached_to_name": doc.name,
        }
    )

    file_doc.save(ignore_permissions=True)

    doc.qr_code = file_doc.file_url
    doc.save(ignore_permissions=True)


# Create Animal Birth From another animal Record
@frappe.whitelist()
def create_animal_birth(source_name, target_doc=None):
    animal_record = frappe.get_doc("Animal Record", source_name)

    target_doc = get_mapped_doc(
        "Animal Record",
        source_name,
        {
            "Animal Record": {
                "doctype": "Animal Record",
            }
        },
        target_doc,
    )

    target_doc.animal_source = "Internal Birth"
    target_doc.mother_tag = animal_record.name
    target_doc.father_tag = None
    target_doc.birth_date = frappe.utils.nowdate()
    target_doc.status = 'Active'
    target_doc.tag_id = None
    target_doc.qr_code = None
    target_doc.sex = None
    target_doc.purchase_price = None
    target_doc.current_weight_kg = 1
    target_doc.carrying_value = None
    target_doc.current_fair_value = None
    target_doc.last_valuation_date = None
    target_doc.cost_to_date = None
    target_doc.treatment_cost_to_date = None
    target_doc.total_cost = None
    target_doc.notes = None

    return target_doc


# Calculate Salaries & Maintenance Costs For Each Animal In The Herd
@frappe.whitelist()
def calculate_accounting_cost(herd_group):
    try:
        # Get Salaries & Maintenance Accounts
        setting = frappe.get_single("Agriculture Setting")

        wages_account = setting.get("wages_and_salaries_account")
        maintenance_account = setting.get("maintenance_account")

        accounts = [a for a in [wages_account, maintenance_account] if a]
        if not accounts:
            return {}

        # Fetch GL Entries
        gl_entries = frappe.db.sql("""
            SELECT
                gl.account,
                gl.posting_date,
                gl.debit - gl.credit AS cost
            FROM `tabGL Entry` gl
            WHERE
                gl.herd_group = %s
                AND gl.is_cancelled = 0
                AND gl.account IN %s
        """, (herd_group, tuple(accounts)), as_dict=True)

        # Fetch Animals
        animal_records = frappe.db.sql("""
            SELECT 
                name,
                status,
                sold_date,
                death_date
            FROM `tabAnimal Record`
            WHERE herd = %s
        """, (herd_group,), as_dict=True)

        # Initialize result dict
        animal_dict = {}
        for ar in animal_records:
            animal_dict[ar.name] = {
                "wages_and_salaries_cost": 0,
                "maintenance_cost": 0
            }

        # Helper: check if animal is applicable for a GL date
        def is_applicable(animal, posting_date):
            if animal.status == "Active":
                return True
            if animal.status == "Dead" and animal.death_date:
                return posting_date <= animal.death_date
            if animal.status == "Sold" and animal.sold_date:
                return posting_date <= animal.sold_date
            return True

        # Process GL Entries
        for gl in gl_entries:
            applicable_animals = [
                ar for ar in animal_records
                if is_applicable(ar, gl.posting_date)
            ]

            if not applicable_animals:
                continue

            cost_per_animal = (gl.cost or 0) / len(applicable_animals)

            for ar in applicable_animals:
                if gl.account == wages_account:
                    animal_dict[ar.name]["wages_and_salaries_cost"] += cost_per_animal
                elif gl.account == maintenance_account:
                    animal_dict[ar.name]["maintenance_cost"] += cost_per_animal

        
        # Update ALL Animal Records (even if cost = 0)
        for ar in animal_records:
            animal_name = ar.name
            costs = animal_dict.get(animal_name, {
                "wages_and_salaries_cost": 0,
                "maintenance_cost": 0
            })

            animal_doc = frappe.get_doc("Animal Record", animal_name)

            if (
                animal_doc.wages_and_salaries_cost != (costs["wages_and_salaries_cost"] or 0) or
                animal_doc.maintenance_cost != (costs["maintenance_cost"] or 0)
            ):
                animal_doc.wages_and_salaries_cost = costs["wages_and_salaries_cost"] or 0
                animal_doc.maintenance_cost = costs["maintenance_cost"] or 0

                animal_doc.save(ignore_permissions=True)

        frappe.db.commit()
        
        return animal_dict

    except Exception:
        # Log Error But Do Not Block GL Creation
        frappe.log_error(
            frappe.get_traceback(),
            "Calculate Accounting Cost Failed"
        )
        return {}

# Update Number of Children
@frappe.whitelist()
def update_number_of_children(animal):
    try:
        if not frappe.db.exists("Animal Record", animal):
            return

        no_of_children = frappe.db.sql("""
            SELECT COUNT(*) AS count
            FROM `tabAnimal Record` ar
            WHERE mother_tag = %s
        """, (animal), as_dict=True)

        no_of_children = no_of_children[0].get('count') if no_of_children else 0

        frappe.set_value("Animal Record", animal, 'number_of_children', no_of_children)
    except Exception:
        frappe.log_erro(f"Error In Update Number Of Children for Animal {animal}")