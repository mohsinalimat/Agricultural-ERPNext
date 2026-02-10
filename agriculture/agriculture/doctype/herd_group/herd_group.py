# Copyright (c) 2025, Ismail Akram and contributors
# For license information, please see license.txt

import frappe

from frappe.model.document import Document
from datetime import date
from frappe import _

class HerdGroup(Document):
    def before_validate(self):
        # Calculte total fields 
        calculate_total(self)

def calculate_total(doc):
    doc.total_fair_value = (doc.total_weight_kg or 0) * (doc.carrying_value or 0)
    doc.total_cost = (
        (doc.purchase_cost or 0) + 
        (doc.medicine_cost_to_date or 0) + 
        (doc.feed_cost_to_date or 0) + 
        (doc.wages_and_salaries_cost or 0) + 
        (doc.maintenance_cost or 0)
    )


@frappe.whitelist()
def update_herd_data(herd_group):
    # Fetch herd group document
    herd_group = frappe.get_doc("Herd Group", herd_group)

    if not herd_group:
        return

    # Aggregate totals from all active animals in this herd
    data = frappe.db.sql("""
        SELECT
            COUNT(animal.name) AS current_heads_number,
            SUM(IFNULL(animal.current_weight_kg, 0)) AS total_weight_kg,
            AVG(IFNULL(animal.current_weight_kg, 0)) AS average_weight,
            SUM(IFNULL(animal.purchase_price, 0)) AS purchase_cost,
            SUM(IFNULL(animal.cost_to_date, 0)) AS feeding_cost,
            SUM(IFNULL(animal.treatment_cost_to_date, 0)) AS treatment_cost,
            SUM(IFNULL(animal.wages_and_salaries_cost, 0)) AS wages_and_salaries_cost,
            SUM(IFNULL(animal.maintenance_cost, 0)) AS maintenance_cost,
            SUM(IFNULL(animal.total_cost, 0)) AS total_cost
        FROM `tabAnimal Record` AS animal
        WHERE
            animal.herd = %s
            AND animal.status = 'Active'
    """, (herd_group.name,), as_dict=True)

    # Update herd group fields with new totals
    if data:
        row = data[0] if data else {}

        herd_group.current_heads_number = round(row.get('current_heads_number', 0) or 0, 2)
        herd_group.total_weight_kg = round(row.get('total_weight_kg', 0.0) or 0.0, 2)
        herd_group.average_weight = round(row.get('average_weight', 0.0) or 0.0, 2)
        herd_group.purchase_cost = round(row.get('purchase_cost', 0.0) or 0.0, 2)
        # herd_group.feed_cost_to_date = round(row.get('feeding_cost', 0.0) or 0.0, 2)
        # herd_group.medicine_cost_to_date = round(row.get('treatment_cost', 0.0) or 0.0, 2)
        herd_group.wages_and_salaries_cost = round(row.get('wages_and_salaries_cost', 0.0) or 0.0, 2)
        herd_group.maintenance_cost = round(row.get('maintenance_cost', 0.0) or 0.0, 2)
        herd_group.total_cost = round(
                                        herd_group.purchase_cost +
                                        herd_group.feed_cost_to_date +
                                        herd_group.medicine_cost_to_date +
                                        herd_group.wages_and_salaries_cost +
                                        herd_group.maintenance_cost, 2
                                    )

    # Save updated herd group values
    herd_group.save(ignore_permissions=True)


@frappe.whitelist()
def update_feeding_and_treatment_cost(herd_group, stock_entry=None):
    # Sync death / sold dates
    frappe.db.sql("""
        UPDATE `tabAnimal Record` ar
        JOIN `tabJournal Entry` je ON je.name = ar.dead_journal_entry
        SET ar.death_date = je.posting_date
        WHERE ar.status = 'Dead'
    """)

    frappe.db.sql("""
        UPDATE `tabAnimal Record` ar
        JOIN `tabSales Invoice Item` sii ON sii.custom_animal_record = ar.name
        JOIN `tabSales Invoice` si ON si.name = sii.parent
        SET ar.sold_date = si.posting_date
        WHERE ar.status = 'Sold'
    """)

    frappe.db.commit()

    # Load animals
    animals = frappe.get_all(
        "Animal Record",
        filters={"herd": herd_group},
        fields=[
            "name", "status", "death_date", "sold_date",
            "animal_source", "birth_date", "purchase_date",
            "purchase_price", "wages_and_salaries_cost",
            "maintenance_cost", "current_weight_kg"
        ]
    )

    animal_names = tuple(a.name for a in animals)
    if not animal_names:
        animal_names = [""]
    placeholders = ", ".join(["%s"] * len(animal_names))

    animal_costs = {
        a.name: {"feeding": 0, "treatment": 0}
        for a in animals
    }

    # Fetch stock entries
    stock_items = frappe.db.sql(f"""
        SELECT
            se.stock_entry_type,
            se.posting_date,
            sed.custom_animal_record,
            sed.amount
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE
            se.docstatus = 1
            AND se.stock_entry_type IN ('Feeding Entry', 'Treatment Entry')
            AND (
                sed.custom_herd_group = %s
                OR sed.custom_animal_record IN ({placeholders})
            )
    """, tuple([herd_group] + list(animal_names)), as_dict=True)

    feeding_cost = 0
    treatment_cost = 0

    # Distribute costs
    for row in stock_items:
        se_type = row.stock_entry_type
        posting_date = row.posting_date
        animal_record = row.custom_animal_record
        amount = row.amount or 0

        if se_type == "Feeding Entry":
            feeding_cost += amount
        else:
            treatment_cost += amount

        # Case 1: single animal
        if animal_record:
            if animal_record not in animal_costs:
                continue

            if se_type == "Feeding Entry":
                animal_costs[animal_record]["feeding"] += amount
            else:
                animal_costs[animal_record]["treatment"] += amount

        # Case 2: herd-level
        else:
            applicable_animals = []

            for ani in animals:
                from_date, to_date = get_active_range(ani)
                if from_date <= posting_date <= to_date:
                    applicable_animals.append(ani.name)

            if not applicable_animals:
                continue

            per_animal = amount / len(applicable_animals)

            for name in applicable_animals:
                if se_type == "Feeding Entry":
                    animal_costs[name]["feeding"] += per_animal
                else:
                    animal_costs[name]["treatment"] += per_animal

    # Update animals
    for animal_name, costs in animal_costs.items():
        frappe.db.sql("""
            UPDATE `tabAnimal Record`
            SET
                cost_to_date = %s,
                treatment_cost_to_date = %s,
                total_cost =
                    IFNULL(purchase_price, 0) +
                    %s +
                    %s +
                    IFNULL(wages_and_salaries_cost, 0) +
                    IFNULL(maintenance_cost, 0)
            WHERE name = %s
        """, (
            costs["feeding"],
            costs["treatment"],
            costs["feeding"],
            costs["treatment"],
            animal_name
        ))

    frappe.db.sql("""
        UPDATE `tabHerd Group` hg
        SET
            feed_cost_to_date = %s,
            medicine_cost_to_date = %s,
            total_cost =
                IFNULL(purchase_cost, 0) +
                %s +
                %s +
                IFNULL(wages_and_salaries_cost, 0) +
                IFNULL(maintenance_cost, 0)
        WHERE name = %s
    """, (
        feeding_cost,
        treatment_cost,
        feeding_cost,
        treatment_cost,
        animal_name
    ))
    frappe.db.commit()  


def get_active_range(animal):
    MIN_DATE = date(2020, 1, 1)
    MAX_DATE = date(2040, 1, 1) 
    
    if animal.animal_source == "Internal Birth":
        from_date = animal.birth_date or MIN_DATE
    else:
        from_date = animal.purchase_date or MIN_DATE

    # TO date
    if animal.status == "Active":
        to_date = MAX_DATE
    elif animal.status == "Sold":
        to_date = animal.sold_date
    elif animal.status == "Dead":
        to_date = animal.death_date
    else:
        to_date = MAX_DATE

    return from_date, to_date
    