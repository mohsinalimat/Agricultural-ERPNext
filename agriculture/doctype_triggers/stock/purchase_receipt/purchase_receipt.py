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
    # Validate all animal tags for Animal items in
    validate_animal_tags_for_items(doc)

@frappe.whitelist()
def validate(doc, method=None):
    pass

@frappe.whitelist()
def on_submit(doc, method=None):
    create_animal_records_for_animal_items(doc)

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
    # Delete all related animal records for Animal items in
    delete_animal_records_for_animal_items(doc)

@frappe.whitelist()
def on_update(doc, method=None):
    pass

# Validate all animal tags for Animal items
def validate_animal_tags_for_items(doc):
    for item in doc.items:
        # Check if the item is an Animal item
        is_animal_item = frappe.db.get_value("Item", item.item_code, "custom_is_animal")
        
        if not is_animal_item:
            continue
        
        # Validate that custom_herd_group is set if the item is an Animal item
        if not item.custom_herd_group:
            frappe.throw(
                f"Animal Item '{item.item_code}' requires a Herd/Group to be specified in row {item.idx}."
            )

        # Validate that the number of Animal Tags matches the quantity
        nom_tags = item.get("custom_animal_tag_ids", []).splitlines() if item.get("custom_animal_tag_ids") else []
        
        # Remove empty lines (if user added extra empty newline)
        nom_tags = [tag.strip() for tag in nom_tags if tag.strip()]
        
        if not nom_tags or len(set(nom_tags)) != item.qty:
            frappe.throw(
                f"The number of Unique Animal Tags provided ({len(set(nom_tags))}) does not match the quantity ({item.qty}) for Item '{item.item_code}' in row {item.idx}."
            )

        update_herd_data(item.custom_herd_group)

# Create Animal records for Animal items in the Purchase Receipt
def create_animal_records_for_animal_items(doc):
    # Validate total male and female With Qty
    for item in doc.items:
        # Check if the item is an Animal item
        is_animal_item = frappe.db.get_value("Item", item.item_code, "custom_is_animal")

        if not is_animal_item:
            continue

        no_of_male = item.custom_no_of_male or 0
        no_of_female = item.custom_no_of_female or 0

        if no_of_male + no_of_female > item.qty:
            frappe.throw(_(f"Row {item.idx}: Number of Male + Number of Female Must be Less Than Or Equall Qty."))

    for item in doc.items:
        # Check if the item is an Animal item
        is_animal_item = frappe.db.get_value("Item", item.item_code, "custom_is_animal")
        
        if not is_animal_item:
            continue
        
        nom_tags = item.get("custom_animal_tag_ids", []).splitlines() if item.get("custom_animal_tag_ids") else []
        
        # Remove empty lines (if user added extra empty newline)
        nom_tags = [tag.strip() for tag in nom_tags if tag.strip()]
        
        no_of_male = item.custom_no_of_male or 0
        no_of_female = item.custom_no_of_female or 0

        for tag in nom_tags:
            # Check if an Animal with this tag already exists
            existing_animal = frappe.db.get_value("Animal Record", {"tag_id": tag})
            if existing_animal:
                link = f"/app/animal-record/{existing_animal}"
                frappe.throw(
                    f"An Animal with Tag '{tag}' already exists: "
                    f"<a href='{link}' target='_blank'>{existing_animal}</a>."
                )
        
        for tag in nom_tags:    
            item_weight = item.weight_per_unit if item.weight_per_unit else 0
            rate = item.rate or 0

            sex = None
            if no_of_male > 0:
                sex = 'Male'
                no_of_male -= 1
            elif no_of_female:
                sex = 'Female'
                no_of_female -= 1
            
            # Create a new Animal record
            animal = frappe.get_doc({
                "doctype": "Animal Record",
                "tag_id": tag,
                "herd": item.custom_herd_group,
                "sex": sex,
                "livestock_master": item.item_code,
                "purchase_date": doc.posting_date,
                "purchase_price": rate,
                "animal_source": "Purchased",
                "purchase_receipt": doc.name,
                "location": doc.set_warehouse,
                "current_weight_kg": item_weight,
                "carrying_value":  rate / item_weight if item_weight else rate,
                "current_fair_value": rate,
                "last_valuation_date": doc.posting_date,
                "status": "Active",
            })
            animal.insert(ignore_permissions=True)

# Delete all related animal records for Animal items in
def delete_animal_records_for_animal_items(doc):
    for item in doc.items:
        # Check if the item is an Animal item
        is_animal_item = frappe.db.get_value("Item", item.item_code, "custom_is_animal")
        
        if not is_animal_item:
            continue
        
        nom_tags = item.get("custom_animal_tag_ids", []).splitlines() if item.get("custom_animal_tag_ids") else []
        
        # Remove empty lines (if user added extra empty newline)
        nom_tags = [tag.strip() for tag in nom_tags if tag.strip()]
        
        for tag in nom_tags:
            animal_name = frappe.db.get_value("Animal Record", {"tag_id": tag})
            if animal_name:
                frappe.delete_doc("Animal Record", animal_name, ignore_permissions=True)