# Copyright (c) 2025, Ismail Akram and contributors
# For license information, please see license.txt

import frappe

from frappe.model.document import Document

from agriculture.agriculture.doctype.herd_group.herd_group import update_herd_data

class AnimalRecord(Document):
	def after_insert(self):
		# Update Herd Group data after inserting Animal Record
		update_herd_data(self.herd)

	def after_delete(self):
		# Update Herd Group data after deleting Animal Record
		update_herd_data(self.herd)
