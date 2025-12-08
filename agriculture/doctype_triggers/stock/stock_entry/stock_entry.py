import frappe

from frappe import _

from agriculture.agriculture.doctype.herd_group.herd_group import update_herd_data

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
    # Update Costs in Animal Records if stock entry typr in ["Feeding Entry", "Treatment Entry"]
    update_animal_totals(doc)

@frappe.whitelist()
def on_cancel(doc, method=None):
    # Update Costs in Animal Records if stock entry typr in ["Feeding Entry", "Treatment Entry"]
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
            update_totals_for_herd(herd_group, amount, doc.stock_entry_type)


def update_totals_for_animal(animal_record, amount, se_type):
    # Fetch animal record document
    animal_doc = frappe.get_doc("Animal Record", animal_record)

    # Recalculate feeding and treatment costs
    purchase_price = animal_doc.purchase_price or 0
    feeding_cost_to_date = (animal_doc.cost_to_date or 0) + (amount if se_type == 'Feeding Entry' else 0)
    treatment_cost_to_date = (animal_doc.treatment_cost_to_date or 0) + (amount if se_type == 'Treatment Entry' else 0)
    total_cost = purchase_price + feeding_cost_to_date + treatment_cost_to_date

    # Update DB directly for performance
    frappe.db.sql("""
        UPDATE `tabAnimal Record`
        SET 
            purchase_price = %s,
            cost_to_date = %s,
            treatment_cost_to_date = %s,
            total_cost = %s
        WHERE name = %s
    """, (purchase_price, feeding_cost_to_date, treatment_cost_to_date, total_cost, animal_record))
    frappe.db.commit()

    # Refresh herd totals based on this animal
    update_herd_data(animal_doc.herd)


def update_totals_for_herd(herd_group, amount, se_type):
    # Get list of active animals in this herd
    animals = frappe.db.sql("""
        SELECT 
            name, 
            purchase_price, 
            cost_to_date, 
            treatment_cost_to_date
        FROM `tabAnimal Record`
        WHERE 
            herd = %s 
            AND status = 'Active'
    """, (herd_group,), as_dict=True)

    if not animals:
        frappe.throw(_("No active animals found in Herd Group '{0}'.".format(herd_group)))

    # Cost per animal (split evenly among all herd animals)
    count = len(animals)
    per_animal_amount = (amount or 0) / count if count else 0

    # Build bulk update data
    for animal in animals:
        purchase_price = animal.purchase_price or 0
        
        # Increase feeding or treatment cost
        feeding_cost = animal.cost_to_date or 0
        treatment_cost = animal.treatment_cost_to_date or 0
        
        if se_type == "Feeding Entry":
            feeding_cost += per_animal_amount
        elif se_type == "Treatment Entry":
            treatment_cost += per_animal_amount

        total_cost = purchase_price + feeding_cost + treatment_cost

        # Update Totals For Animal
        frappe.db.sql("""
            UPDATE `tabAnimal Record`
            SET 
                purchase_price = %s,
                cost_to_date = %s,
                treatment_cost_to_date = %s,
                total_cost = %s
            WHERE name = %s
        """, (purchase_price, feeding_cost, treatment_cost, total_cost, animal.name))

    # Commit Cchanges To Database
    frappe.db.commit()

    # Update totals for herd group
    update_herd_data(herd_group)
