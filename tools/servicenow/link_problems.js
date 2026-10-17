/*
 * OpsIntel - follow-up to seed_incidents.js for instances where problem creation was refused
 * by data policies: creates the two planted problem records and links the matching seeded
 * incidents to them. Idempotent (skips if seeded problems already exist).
 * Run in: System Definition > Scripts - Background (scope: global), as admin.
 */
(function linkOpsIntelProblems() {
    var TAG = 'opsintel_seed';
    var existing = new GlideRecord('problem');
    existing.addQuery('correlation_id', TAG);
    existing.query();
    if (existing.hasNext()) { gs.print('ABORT: seeded problems already exist.'); return; }

    function groupId(name) { var g = new GlideRecord('sys_user_group'); return g.get('name', name) ? g.getUniqueValue() : ''; }
    function firstMember(gid) {
        var m = new GlideRecord('sys_user_grmember'); m.addQuery('group', gid); m.addQuery('user.active', true); m.setLimit(1); m.query();
        if (m.next()) return m.getValue('user');
        var a = new GlideRecord('sys_user'); return a.get('user_name', 'admin') ? a.getUniqueValue() : '';
    }
    function problem(shortDesc, desc, cause, fix, grpName, opened, state, ciQuery) {
        var gid = groupId(grpName);
        var p = new GlideRecord('problem');
        p.initialize();
        p.setWorkflow(false);
        p.autoSysFields(false);
        p.setValue('short_description', shortDesc);
        p.setValue('description', desc);
        p.setValue('cause_notes', cause);
        p.setValue('workaround', fix);
        p.setValue('fix_notes', fix);
        p.setValue('assignment_group', gid);
        p.setValue('assigned_to', firstMember(gid));
        if (state >= 106) p.setValue('resolution_code', 'fix_applied');
        p.setValue('priority', 2);
        p.setValue('state', state);
        p.setValue('opened_at', opened);
        p.setValue('sys_created_on', opened);
        p.setValue('sys_updated_on', new GlideDateTime().getValue());
        p.setValue('sys_created_by', TAG);
        p.setValue('sys_updated_by', TAG);
        p.setValue('correlation_id', TAG);
        var id = p.insert();
        if (!id) gs.print('Problem insert refused: ' + shortDesc);
        return id;
    }
    function link(problemId, encodedQuery, note) {
        var n = 0, inc = new GlideRecord('incident');
        inc.addEncodedQuery('correlation_id=' + TAG + '^' + encodedQuery);
        inc.query();
        while (inc.next()) {
            inc.setWorkflow(false);
            inc.autoSysFields(false);
            inc.setValue('problem_id', problemId);
            if (inc.getValue('resolved_at')) inc.setValue('close_notes', note);
            inc.update();
            n++;
        }
        return n;
    }
    var vpn = problem('VPN concentrator drops tunnels under peak load',
        'Recurring VPN disconnections since July 2026, concentrated on the VPN concentrators. Correlates with home-working peaks (Mon-Thu 08:00-10:00).',
        'Firmware defect in the VPN concentrator cluster exhausts the session table under load; vendor bug confirmed, fixed in next maintenance release.',
        'Fail users over to secondary concentrator and clear stale sessions (see network runbook).',
        'Network', '2026-07-21 09:00:00', 104);
    var mail = problem('Mail gateway rejecting external TLS connections',
        'Spike of email delivery incidents 8-19 Sep 2026 affecting Email and OWA users.',
        'Intermediate certificate missing from the mail gateway TLS chain after certificate renewal.',
        'Re-issued certificate chain on the mail gateway; affected partner domains routed via secondary gateway meanwhile.',
        'Software', '2026-09-10 09:00:00', 106);
    var nv = vpn ? link(vpn, 'category=network^opened_at>=2026-07-01 00:00:00^short_descriptionLIKEVPN', 'Workaround applied; linked to problem for permanent fix.') : 0;
    var nm = mail ? link(mail, 'category=software^opened_at>=2026-09-08 00:00:00^opened_at<=2026-09-20 00:00:00^short_descriptionLIKETLS^ORshort_descriptionLIKErejected^ORshort_descriptionLIKEstuck in queue', 'Resolved by problem fix: certificate chain corrected.') : 0;
    gs.print('Problems created: VPN ' + vpn + ', Mail ' + mail + ' | incidents linked: VPN ' + nv + ', Mail ' + nm);
})();
