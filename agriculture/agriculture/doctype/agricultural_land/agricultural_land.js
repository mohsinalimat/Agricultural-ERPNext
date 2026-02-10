// Copyright (c) 2026, Ismail Akram and contributors
// For license information, please see license.txt

frappe.ui.form.on("Agricultural Land", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.status == "Crop Cycle") {
			frm.add_custom_button(
				__("Sales Invoice"),
				function () {
					frappe.model.open_mapped_doc({
						method: "agriculture.agriculture.doctype.animal_record.animal_record.create_sales_invoice",
						frm: frm,
					});
				},
				__("Create"),
			);
		}
	},
});
