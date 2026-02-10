# Copyright (c) 2026, Ismail Akram and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AgriculturalLand(Document):
	def before_validate(self):
		self.calclate_totals()


	def calclate_totals(self):
		self.total_of_cycles_completed = len(self.cycles or [])
		self.number_of_cycles_remaining = (self.total_number_of_cycles or 0) - (self.total_of_cycles_completed or 0)
		self.seed_cost_per_cycle = (self.seed_cost or 0) / (self.total_number_of_cycles or 1) if self.total_number_of_cycles else 0
		self.remaining_cost = (self.number_of_cycles_remaining) * self.seed_cost_per_cycle
