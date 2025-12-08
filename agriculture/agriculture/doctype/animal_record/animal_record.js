frappe.ui.form.on("Animal Record", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.status == "Active") {
			frm.add_custom_button(
				__("Sales Invoice"),
				function () {
					frappe.model.open_mapped_doc({
						method: "agriculture.agriculture.doctype.animal_record.animal_record.create_sales_invoice",
						frm: frm,
					});
				},
				__("Create")
			);
		}

		if (!frm.is_new() && frm.doc.status == "Active") {
			let options = [];

			if (frm.doc.animal_source == "Internal Birth" && !frm.doc.birth_journal_entry) {
				options.push({ label: "Birth Entry", value: "Birth" });
			}
			if (!frm.doc.dead_journal_entry) {
				options.push({ label: "Dead Entry", value: "Dead" });
			}

			frm.add_custom_button(
				__("Journal Entry"),
				function () {
					// Open selection dialog
					let d = new frappe.ui.Dialog({
						title: __("Select Journal Entry Type"),
						fields: [
							{
								label: "Entry Type",
								fieldname: "entry_type",
								fieldtype: "Select",
								options: options,
								reqd: 1,
							},
						],
						primary_action_label: __("Create"),
						primary_action(values) {
							if (!values.entry_type) {
								frappe.msgprint("Please select an entry type.");
								return;
							}

							d.hide();

							frappe.call({
								method: "agriculture.agriculture.doctype.animal_record.animal_record.create_journal_entry",
								args: {
									animal_record: frm.doc.name,
									entry_type: values.entry_type,
								},
								callback: function (r) {
									if (!r.exc) {
										frappe.msgprint(__("Journal Entry Created Successfully"));
										frm.reload_doc();
									}
								},
							});
						},
					});

					d.show();
				},
				__("Create")
			);
		}
	},
});
