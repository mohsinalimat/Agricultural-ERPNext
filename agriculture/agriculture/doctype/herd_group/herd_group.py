# Copyright (c) 2025, Ismail Akram and contributors
# For license information, please see license.txt

import frappe

from frappe.model.document import Document
from frappe import _

class HerdGroup(Document):
    def before_validate(self):
        # Calculte total fields 
        calculate_total(self)


def calculate_total(doc):
    doc.total_fair_value = (doc.total_weight_kg or 0) * (doc.carrying_value or 0)
    doc.total_cost = (doc.purchase_cost or 0) + (doc.medicine_cost_to_date or 0) + (doc.feed_cost_to_date or 0)


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
        herd_group.current_heads_number = data[0].get('current_heads_number', 0) or 0
        herd_group.total_weight_kg = data[0].get('total_weight_kg', 0.0) or 0.0
        herd_group.average_weight = data[0].get('average_weight', 0.0) or 0.0
        herd_group.purchase_cost = data[0].get('purchase_cost', 0.0) or 0.0
        herd_group.feed_cost_to_date = data[0].get('feeding_cost', 0.0) or 0.0
        herd_group.medicine_cost_to_date = data[0].get('treatment_cost', 0.0) or 0.0
        herd_group.wages_and_salaries_cost = data[0].get('wages_and_salaries_cost', 0.0) or 0.0
        herd_group.maintenance_cost = data[0].get('maintenance_cost', 0.0) or 0.0
        herd_group.total_cost = data[0].get('total_cost', 0.0) or 0.0

    # Save updated herd group values
    herd_group.save(ignore_permissions=True)
