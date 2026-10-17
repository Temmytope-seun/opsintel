/*
 * OpsIntel - remove everything created by seed_incidents.js.
 * Run in: System Definition > Scripts - Background (scope: global), as admin.
 * Deletes ONLY records whose correlation_id is 'opsintel_seed' (incidents and problems).
 * Set DRY_RUN = false to actually delete.
 */
(function removeOpsIntelSeed() {
    var TAG = 'opsintel_seed';
    var DRY_RUN = true;
    var tables = ['incident', 'problem'];
    for (var i = 0; i < tables.length; i++) {
        var g = new GlideRecord(tables[i]);
        g.addQuery('correlation_id', TAG);
        g.query();
        var n = g.getRowCount();
        if (DRY_RUN) {
            gs.print('[dry run] would delete ' + n + ' ' + tables[i] + ' records tagged ' + TAG);
        } else {
            g.setWorkflow(false);
            g.deleteMultiple();
            gs.print('Deleted ' + n + ' ' + tables[i] + ' records tagged ' + TAG);
        }
    }
})();
