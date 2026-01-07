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
    pass
@frappe.whitelist()
def validate(doc, method=None):
    pass

@frappe.whitelist()
def on_submit(doc, method=None):
    update_animal_herd_links(doc, action='Submit')

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
    update_animal_herd_links(doc, action='Cancel')

@frappe.whitelist()
def on_update(doc, method=None):
    pass

# Validate Animal Record and add create links
def update_animal_herd_links(doc, action='Submit'):
    if not doc.custom_animal_record or not doc.custom_animal_state:
        return

    animal_record = doc.custom_animal_record
    animal_state = doc.custom_animal_state

    animal_doc = frappe.get_doc("Animal Record", doc.custom_animal_record)
    
    # Validate if can submit 
    if action == 'Submit' and animal_doc.status != 'Active' and animal_state in ['Sold', 'Dead']:
        frappe.throw(_("Can't Submit Journal Entry, Animal Record Isn't Active."))
    if action == 'Submit' and animal_state == 'Birth' and animal_doc.birth_journal_entry:
        je_link = get_link_to_form("Journal Entry", animal_doc.birth_journal_entry)
        frappe.throw(_(
            "Can't Submit Journal Entry, Current Animal Record is already linked with Journal Entry {0}."
        ).format(je_link))
    if action == 'Submit' and animal_state == 'Dead' and animal_doc.dead_journal_entry:
        je_link = get_link_to_form("Journal Entry", animal_doc.dead_journal_entry)
        frappe.throw(_(
            "Can't Submit Journal Entry, Current Animal Record is already linked with Journal Entry {0}."
        ).format(je_link))
        
    # Update Links
    if animal_state == "Sold":
        frappe.set_value('Animal Record', animal_record, 'status', 'Sold' if action == 'Submit' else 'Active')
        frappe.set_value('Animal Record', animal_record, 'sold_date', doc.posting_date if action == 'Submit' else None)
    if animal_state == 'Birth':
        frappe.set_value('Animal Record', animal_record, 'birth_journal_entry', doc.name if action == 'Submit' else None)
        frappe.set_value('Animal Record', animal_record, 'birth_date', doc.posting_date if action == 'Submit' else None)
    if animal_state == 'Dead':
        frappe.set_value('Animal Record', animal_record, 'status', 'Dead' if action == 'Submit' else 'Active')
        frappe.set_value('Animal Record', animal_record, 'dead_journal_entry', doc.name if action == 'Submit' else None)
        frappe.set_value('Animal Record', animal_record, 'death_date', doc.posting_date if action == 'Submit' else None)
