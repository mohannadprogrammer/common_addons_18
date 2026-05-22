/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

export class ClinicRun extends Component {
    static template = "clinic_run.main";

    setup() {
        this.http = useService("http");
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            shifts: [],
            filter: "all",
            stats: { total: 0, draft: 0, open: 0, closed: 0 },
        });

        onWillStart(async () => {
            await this.loadShifts();
        });
    }

    async loadShifts() {
        const result = await this.http.post("/clinic_run/get_shifts", {});
        this.state.shifts = result.shifts;
        this.state.stats = result.stats;
    }

    get filteredShifts() {
        if (this.state.filter === "all") return this.state.shifts;
        return this.state.shifts.filter(s => s.state === this.state.filter);
    }

    setFilter(filter) {
        this.state.filter = filter;
    }

    openShift(shiftId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Appointments",
            res_model: "clinic.appointment",
            view_mode: "kanban,list,form",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            domain: [["shift_id", "=", shiftId]],
            context: { default_shift_id: shiftId },
        });
    }

    openNewShift() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "clinic.shift",
            view_mode: "form",
            views: [[false, "form"]],
            context: { default_state: "draft" },
        });
    }

    async confirmAction(shiftId, actionType) {
        if (actionType === "open_shift") {
            if (!confirm("Start this shift?")) return;
            try {
                await this.orm.call("clinic.shift", "action_open", [[shiftId]]);
                await this.loadShifts();
            } catch (e) {}
        }
        if (actionType === "close_shift") {
            try {
                const result = await this.orm.call("clinic.shift", "action_close", [[shiftId]]);
                if (result) {
                    this.action.doAction(result);
                }
            } catch (e) {}
        }
    }

    closeApp() {
        this.action.doAction({ type: "ir.actions.act_window_close" });
    }
}

registry.category("actions").add("clinic_run", ClinicRun);
