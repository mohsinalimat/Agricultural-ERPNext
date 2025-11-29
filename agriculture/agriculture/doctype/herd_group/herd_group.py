# Copyright (c) 2025, Ismail Akram and contributors
# For license information, please see license.txt

import frappe

from frappe.model.document import Document
from frappe import _

class HerdGroup(Document):
    pass

@frappe.whitelist()
def update_herd_data(herd_group):
    herd_group = frappe.get_doc("Herd Group", herd_group)

    if not herd_group:
        return

    data = frappe.db.sql("""
        SELECT
            COUNT(animal.name) AS current_heads_number,
            SUM(IFNULL(animal.current_weight_kg, 0)) AS total_weight_kg,
            AVG(animal.current_weight_kg) AS average_weight
        FROM `tabAnimal Record` AS animal
        WHERE
            animal.herd = %s
            AND animal.status = 'Active'
    """, (herd_group.name,), as_dict=True)

    if data:
        herd_group.current_heads_number = data[0].get('current_heads_number', 0) or 0
        herd_group.total_weight_kg = data[0].get('total_weight_kg', 0.0) or 0.0
        herd_group.average_weight = data[0].get('average_weight', 0.0) or 0.0
        
    herd_group.save(ignore_permissions=True)