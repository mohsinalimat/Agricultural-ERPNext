frappe.listview_settings["Animal Record"] = {
	onload(listview) {
		// Add a visible list view button for bulk fair value updates.
		listview.page.add_inner_button(__("Update Fair Value"), () => {
			const selected = listview.get_checked_items().map((row) => row.name);

			if (!selected.length) {
				frappe.msgprint(__("Please select at least one Animal Record."));
				return;
			}

			const dialog = new frappe.ui.Dialog({
				title: __("Enter Valuation Details"),
				fields: [
					{
						label: __("Current Weight (kg)"),
						fieldname: "current_weight",
						fieldtype: "Float",
						reqd: 1,
					},
					{
						label: __("Current Carrying Value"),
						fieldname: "carrying_value",
						fieldtype: "Float",
						reqd: 1,
					},
					{
						label: __("Valuation Date"),
						fieldname: "valuation_date",
						fieldtype: "Date",
						reqd: 1,
					},
				],
				primary_action_label: __("Submit"),
				primary_action(values) {
					frappe.call({
						method: "agriculture.agriculture.doctype.animal_record.animal_record.bulk_update_fair_value",
						args: {
							animal_records: selected,
							data: values,
						},
						callback: (r) => {
							if (r.exc) {
								return;
							}

							const result = r.message || {};
							const failed = result.failed || [];
							const updated = result.updated || 0;
							const skipped = result.skipped || [];

							if (updated.length) {
								frappe.msgprint(__("Updated {0} Record(s).", [updated]));
							}
							if (failed.length) {
								frappe.msgprint(__("Failed Record(s): {1}", [failed.join(", ")]));
							}
							if (skipped.length) {
								frappe.msgprint(
									__("Skipped Record(s) (not Active): {1}", [skipped.join(", ")])
								);
							}

							listview.refresh();
						},
					});

					dialog.hide();
				},
			});

			dialog.show();
		});

		// Build a single draft Sales Invoice using selected records as items.
		listview.page.add_inner_button(__("Create Sales Invoice"), () => {
			const selected = listview.get_checked_items().map((row) => row.name);

			if (!selected.length) {
				frappe.msgprint(__("Please select at least one Animal Record."));
				return;
			}

			frappe.call({
				method: "agriculture.agriculture.doctype.animal_record.animal_record.bulk_create_sales_invoice",
				args: {
					animal_records: selected,
				},
				callback: (r) => {
					if (!r.message) return;

					frappe.model.sync(r.message);
					frappe.set_route("Form", r.message.doctype, r.message.name);
				},
			});
		});
	},
};
