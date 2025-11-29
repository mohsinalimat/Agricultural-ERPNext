frappe.ui.form.on("Herd Group", {
	refresh(frm) {
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__("Update Herd Data"), function () {
				frappe.call({
					method: "agriculture.agriculture.doctype.herd_group.herd_group.update_herd_data",
					args: { herd_group: frm.doc.name },
					callback: function (r) {
						frappe.msgprint(_("Herd Group data updated successfully."));
						frm.reload_doc();
					},
				});
			});
		}
	},
});
