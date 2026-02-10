import frappe

from frappe import _
from datetime import datetime
from agriculture.agriculture.doctype.herd_group.herd_group import get_active_range

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
    pass
@frappe.whitelist()
def validate(doc, method=None):
    pass

@frappe.whitelist()
def on_submit(doc, method=None):
    # Update Costs in Animal Records if stock entry type in ["Feeding Entry", "Treatment Entry"]
    update_animal_totals(doc)

@frappe.whitelist()
def on_cancel(doc, method=None):
    # Update Costs in Animal Records if stock entry type in ["Feeding Entry", "Treatment Entry"]
    update_animal_totals(doc, 1)

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
    pass


def update_animal_totals(doc, is_cancel=0):
    posting_date = doc.posting_date
    if isinstance(posting_date, str):
        posting_date = datetime.strptime(posting_date, "%Y-%m-%d").date()
        
    # Only run for Feeding or Treatment entries
    if doc.stock_entry_type not in ['Feeding Entry', 'Treatment Entry']:
        return

    # Validate that each row has either Herd Group or Animal Record
    for row in doc.items:
        herd_group = row.get('custom_herd_group')
        animal_record = row.get('custom_animal_record')
        
        if not herd_group and not animal_record:
            frappe.throw(_(f"Row {row.idx}: Herd Group or Animal Record is Required For Stock Entry Type '{doc.stock_entry_type}'"))

    # Process each row and update totals
    for row in doc.items:
        herd_group = row.get('custom_herd_group')
        animal_record = row.get('custom_animal_record')
        amount = (row.get('amount', 0) or 0) * (-1 if is_cancel else 1)
        
        # Update animal or herd totals based on the row
        if animal_record:
            update_totals_for_animal(animal_record, amount, doc.stock_entry_type)
        else:
            update_totals_for_herd(herd_group, amount, doc.stock_entry_type, posting_date)


def update_totals_for_animal(animal_record, amount, se_type):
    # Fetch animal doc to get the herd
    animal_doc = frappe.get_doc("Animal Record", animal_record)
    herd_group = animal_doc.herd

    feeding_cost = amount if se_type == "Feeding Entry" else 0
    treatment_cost = amount if se_type == "Treatment Entry" else 0
    total_cost = feeding_cost + treatment_cost

    # Update animal totals
    frappe.db.sql("""
        UPDATE `tabAnimal Record`
        SET 
            cost_to_date = IFNULL(cost_to_date,0) + %s, 
            treatment_cost_to_date = IFNULL(treatment_cost_to_date,0) + %s,
            total_cost = IFNULL(total_cost,0) + %s
        WHERE name = %s
    """, (feeding_cost, treatment_cost, total_cost, animal_record))

    # Update herd totals
    frappe.db.sql("""
        UPDATE `tabHerd Group`
        SET 
            feed_cost_to_date = IFNULL(feed_cost_to_date,0) + %s, 
            medicine_cost_to_date = IFNULL(medicine_cost_to_date,0) + %s,
            total_cost = IFNULL(total_cost,0) + %s
        WHERE name = %s
    """, (feeding_cost, treatment_cost, total_cost, herd_group))

    frappe.db.commit()


def update_totals_for_herd(herd_group, amount, se_type, posting_date):
    # Fetch all animals in this herd
    animals = frappe.get_all(
        "Animal Record",
        filters={"herd": herd_group},
        fields=[
            "name", "status", "death_date", "sold_date",
            "animal_source", "birth_date", "purchase_date",
            "purchase_price", "wages_and_salaries_cost", "maintenance_cost",
            "cost_to_date", "treatment_cost_to_date"
        ]
    )

    # Determine which animals are active at the posting_date
    active_animals = []
    for ani in animals:
        from_date, to_date = get_active_range(ani)
        if from_date <= posting_date <= to_date:
            active_animals.append(ani)

    if not active_animals:
        return

    # Split amount evenly among active animals
    per_animal_amount = (amount or 0) / len(active_animals)

    total_feeding = 0
    total_treatment = 0

    for ani in active_animals:
        feeding_cost = ani.cost_to_date or 0
        treatment_cost = ani.treatment_cost_to_date or 0

        if se_type == "Feeding Entry":
            feeding_cost += per_animal_amount
            total_feeding += per_animal_amount
        elif se_type == "Treatment Entry":
            treatment_cost += per_animal_amount
            total_treatment += per_animal_amount

        total_cost = (ani.purchase_price or 0) + feeding_cost + treatment_cost + (ani.wages_and_salaries_cost or 0) + (ani.maintenance_cost or 0)

        # Update each animal
        frappe.db.sql("""
            UPDATE `tabAnimal Record`
            SET 
                cost_to_date = %s,
                treatment_cost_to_date = %s,
                total_cost = %s
            WHERE name = %s
        """, (feeding_cost, treatment_cost, total_cost, ani.name))

    # Update herd totals
    frappe.db.sql("""
        UPDATE `tabHerd Group`
        SET 
            feed_cost_to_date = IFNULL(feed_cost_to_date,0) + %s,
            medicine_cost_to_date = IFNULL(medicine_cost_to_date,0) + %s,
            total_cost = IFNULL(total_cost,0) + %s
        WHERE name = %s
    """, (total_feeding, total_treatment, total_feeding + total_treatment, herd_group))

    frappe.db.commit()
