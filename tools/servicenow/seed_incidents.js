/*
 * OpsIntel - seed a ServiceNow developer instance with a year of realistic incident history.
 *
 * Run in: System Definition > Scripts - Background (scope: global), as admin.
 * Idempotent: refuses to run if records tagged 'opsintel_seed' already exist.
 * Remove everything it created with tools/servicenow/remove_seed.js.
 *
 * What it creates (deterministic - same data every run):
 *   ~1,400 incidents over the 12 months to today, on the instance's own business services,
 *   CIs, groups, users and companies; business-hours / weekday arrival pattern; priority from
 *   impact x urgency; lognormal resolution times around P1-P4 targets (~10% breach baseline);
 *   realistic states (closed / resolved / in progress / on hold / new).
 *   Planted signals for the analytics to find:
 *     1. VPN tunnel drops (Jul 2026 -> today): recurring, long-running, linked to a problem record.
 *     2. Mail gateway TLS incident spike (8-19 Sep 2026) on Email / OWA, linked to a problem.
 *     3. Retail POS hardware peak around Black Friday (20 Nov - 3 Dec 2025).
 *   ~10% of incidents have no business service and ~15% no company (real-world gaps).
 * Business rules / workflows are skipped (setWorkflow(false)) so no notifications, SLAs or
 * approvals fire and historical dates are kept (autoSysFields(false)).
 */
(function seedOpsIntel() {
    var TAG = 'opsintel_seed';
    var DAYS = 365;

    var already = new GlideAggregate('task');
    already.addQuery('correlation_id', TAG);
    already.addAggregate('COUNT');
    already.query();
    if (already.next() && parseInt(already.getAggregate('COUNT'), 10) > 0) {
        gs.print('ABORT: ' + already.getAggregate('COUNT') + ' records tagged ' + TAG + ' already exist. Run remove_seed.js first.');
        return;
    }

    // ------------------------------------------------------------------ deterministic random
    var s = 20261017;
    function rnd() { s = (s * 1103515245 + 12345) % 2147483648; return s / 2147483648; }
    function pick(a) { return a[Math.floor(rnd() * a.length)]; }
    function weighted(pairs) {
        var t = 0, i;
        for (i = 0; i < pairs.length; i++) t += pairs[i][1];
        var r = rnd() * t;
        for (i = 0; i < pairs.length; i++) { r -= pairs[i][1]; if (r <= 0) return pairs[i][0]; }
        return pairs[pairs.length - 1][0];
    }
    function poisson(lambda) { var L = Math.exp(-lambda), k = 0, p = 1; do { k++; p *= rnd(); } while (p > L); return k - 1; }
    function lognormal(mu, sigma) {
        var u1 = rnd() || 1e-9, u2 = rnd();
        return Math.exp(mu + sigma * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2));
    }

    // ------------------------------------------------------------------ instance reference data
    function rows(table, query, limit) {
        var out = [], g = new GlideRecord(table);
        if (query) g.addEncodedQuery(query);
        g.setLimit(limit || 500);
        g.query();
        while (g.next()) out.push(g.getUniqueValue());
        return out;
    }
    function byName(table, names) {
        var out = [];
        for (var i = 0; i < names.length; i++) {
            var g = new GlideRecord(table);
            if (g.get('name', names[i])) out.push(g.getUniqueValue());
        }
        return out;
    }
    function group(names) { var g = byName('sys_user_group', names); return g.length ? g[0] : ''; }
    function members(groupId) {
        var out = [], m = new GlideRecord('sys_user_grmember');
        m.addQuery('group', groupId);
        m.addQuery('user.active', true);
        m.query();
        while (m.next()) out.push(m.getValue('user'));
        return out;
    }
    function choices(element, dependent) {
        var out = [], c = new GlideRecord('sys_choice');
        c.addQuery('name', 'incident');
        c.addQuery('element', element);
        c.addQuery('inactive', false);
        c.addQuery('language', 'en');
        if (dependent) c.addQuery('dependent_value', dependent);
        c.query();
        while (c.next()) out.push({ value: c.getValue('value'), label: c.getValue('label') });
        return out;
    }
    function firstChoice(element, preferredLabels, fallback) {
        var list = choices(element);
        for (var p = 0; p < preferredLabels.length; p++)
            for (var i = 0; i < list.length; i++)
                if (list[i].label.toLowerCase() === preferredLabels[p].toLowerCase()) return list[i].value;
        return list.length ? list[0].value : fallback;
    }
    function validSub(category, wanted) {
        var list = choices('subcategory', category);
        if (!list.length) return wanted;
        for (var i = 0; i < list.length; i++) if (list[i].value === wanted) return wanted;
        return list[Math.floor(rnd() * list.length)].value;
    }

    var callers = rows('sys_user', 'active=true^web_service_access_only=false^user_nameNOT LIKEadmin', 400);
    var companies = rows('core_company', 'customer=true', 80);
    if (companies.length < 10) companies = rows('core_company', '', 80);
    var deskUser = byName('sys_user', ['System Administrator']);

    var CLOSE = {
        solved: firstChoice('close_code', ['Solution provided', 'Solved (Permanently)', 'Solved Remotely (Permanently)'], 'Solved (Permanently)'),
        remote: firstChoice('close_code', ['Solved Remotely (Permanently)', 'Solution provided'], 'Solved Remotely (Permanently)'),
        workaround: firstChoice('close_code', ['Workaround provided', 'Solved (Work Around)', 'Solved Remotely (Work Around)'], 'Solved (Work Around)'),
        caller: firstChoice('close_code', ['Resolved by caller', 'Closed/Resolved by Caller'], 'Closed/Resolved by Caller'),
        user: firstChoice('close_code', ['User error', 'Not Solved (Not Reproducible)'], 'Not Solved (Not Reproducible)'),
        problem: firstChoice('close_code', ['Resolved by problem', 'Known error', 'Workaround provided', 'Solved (Work Around)'], 'Solved (Work Around)')
    };
    var CONTACT = [];
    var ct = choices('contact_type');
    var wantContact = { 'phone': 30, 'email': 25, 'self-service': 30, 'walk-in': 5, 'virtual_agent': 5, 'monitoring': 10, 'event': 10 };
    for (var ci = 0; ci < ct.length; ci++) if (wantContact[ct[ci].value]) CONTACT.push([ct[ci].value, wantContact[ct[ci].value]]);
    if (!CONTACT.length) CONTACT = [['phone', 1], ['email', 1], ['self-service', 1]];

    // ------------------------------------------------------------------ incident profiles
    var P = {
        network: {
            group: group(['Network']), cis: rows('cmdb_ci_netgear', '', 50),
            services: byName('cmdb_ci_service', ['IT Services', 'E-Commerce', 'Retail POS (Point of Sale)', 'Bond Trading', 'Electronic Messaging']),
            subs: [['vpn', 25], ['wireless', 30], ['dns', 15], ['dhcp', 15], ['ip address', 15]],
            text: {
                'vpn': ['VPN disconnects every few minutes when working from home', 'Cannot establish VPN tunnel - authentication succeeds then drops'],
                'wireless': ['Wi-Fi keeps dropping in meeting rooms on floor 3', 'Very slow wireless in the trading floor area'],
                'dns': ['Internal sites not resolving - DNS lookup failures', 'Intermittent DNS timeouts for e-commerce backend'],
                'dhcp': ['Laptop not getting an IP address on the office LAN', 'DHCP scope exhausted in branch office'],
                'ip address': ['IP address conflict reported on POS terminal', 'Static IP needed for new printer']
            }
        },
        hardware: {
            group: group(['Hardware', 'Field Services']), cis: rows('cmdb_ci_computer', '', 300),
            services: byName('cmdb_ci_service', ['IT Services', 'Retail POS (Point of Sale)', 'Blackberry', 'Windows Mobile']),
            subs: [['disk', 20], ['monitor', 20], ['keyboard', 15], ['mouse', 10], ['memory', 15], ['cpu', 20]],
            text: {
                'disk': ['Laptop disk nearly full - SMART warning on boot', 'Hard drive failure on finance workstation'],
                'monitor': ['Second monitor flickering and goes black', 'No display signal after docking laptop'],
                'keyboard': ['Several keys not responding on laptop keyboard', 'Wireless keyboard lag on POS till'],
                'mouse': ['Mouse cursor jumping erratically', 'Bluetooth mouse will not pair'],
                'memory': ['Machine very slow, memory usage constantly at 95%', 'Blue screen - memory management error'],
                'cpu': ['Laptop fan loud and CPU at 100% after update', 'POS terminal overheating and rebooting']
            }
        },
        software: {
            group: group(['Software', 'Application Development']), cis: rows('cmdb_ci_appl', '', 50),
            services: byName('cmdb_ci_service', ['Email', 'Outlook Web Access (OWA)', 'SAP Financial Accounting', 'SAP Sales and Distribution',
                'SAP Human Resources', 'PeopleSoft CRM', 'PeopleSoft Financials', 'Sales Force Automation', 'Slack', 'Workday Enterprise Services']),
            subs: [['email', 45], ['os', 55]],
            text: {
                'email': ['Outlook not syncing - emails stuck in outbox', 'Shared mailbox not visible after migration', 'Calendar invites not received from external partners'],
                'os': ['Application crashes on start after Windows update', 'Cannot install approved software from portal', 'SAP GUI freezes when running month-end report', 'PeopleSoft page returns error 500 for some users']
            }
        },
        database: {
            group: group(['Database', 'NY DB', 'Database Atlanta']), cis: rows('cmdb_ci_database', '', 50),
            services: byName('cmdb_ci_service', ['SAP Financial Accounting', 'PeopleSoft Financials', 'Bond Trading', 'Securities Lending']),
            subs: [['oracle', 40], ['ms sql server', 40], ['db2', 20]],
            text: {
                'oracle': ['Oracle tablespace above 90% on finance DB', 'Long-running query blocking SAP batch jobs'],
                'ms sql server': ['SQL Server deadlocks during trade settlement', 'Database backup job failed overnight'],
                'db2': ['DB2 connection pool exhausted', 'Replication lag on reporting replica']
            }
        },
        inquiry: {
            group: group(['Service Desk', 'Help Desk']), cis: [],
            services: byName('cmdb_ci_service', ['Email', 'IT Services', 'Workday Enterprise Services', 'PeopleSoft HRMS']),
            subs: [['internal application', 50], ['email', 30], ['antivirus', 20]],
            text: {
                'internal application': ['How do I request access to the reporting portal?', 'Password reset for Workday', 'Need help exporting a report to Excel'],
                'email': ['How to set up out-of-office on mobile', 'Request to increase mailbox size'],
                'antivirus': ['Antivirus quarantined a legitimate file', 'Pop-up warning about outdated antivirus definitions']
            }
        }
    };
    var MIX = [['inquiry', 34], ['software', 26], ['hardware', 18], ['network', 14], ['database', 8]];
    for (var k in P) if (P[k].group) P[k].members = members(P[k].group);

    // impact x urgency -> priority (ServiceNow default lookup); targets in hours
    var PRIO = { '11': 1, '12': 2, '21': 2, '13': 3, '22': 3, '31': 3, '23': 4, '32': 4, '33': 5 };
    var TARGET = { 1: 4, 2: 8, 3: 24, 4: 72, 5: 72 };

    // ------------------------------------------------------------------ problems (planted signals)
    var now = new GlideDateTime();
    var nowMs = now.getNumericValue();
    var DAY = 86400000, HOUR = 3600000;
    function dt(ms) { var g = new GlideDateTime(); g.setNumericValue(ms); return g; }
    function dts(ms) { return dt(ms).getValue(); }   // 'yyyy-MM-dd HH:mm:ss' UTC, as setValue expects
    function ms(isoDate) { var g = new GlideDateTime(); g.setValue(isoDate + ' 00:00:00'); return g.getNumericValue(); }

    function problem(shortDesc, desc, cause, workaround, ci, grp, openedMs, state) {
        var p = new GlideRecord('problem');
        p.initialize();
        p.setWorkflow(false);
        p.autoSysFields(false);
        p.setValue('short_description', shortDesc);
        p.setValue('description', desc);
        p.setValue('cause_notes', cause);
        p.setValue('workaround', workaround);
        p.setValue('cmdb_ci', ci);
        p.setValue('assignment_group', grp);
        // Data policies on problem require these for 'Fix in Progress' / 'Resolved'.
        var who = members(grp);
        p.setValue('assigned_to', who.length ? who[0] : (deskUser.length ? deskUser[0] : ''));
        p.setValue('fix_notes', workaround);
        if (state >= 106) p.setValue('resolution_code', 'fix_applied');
        p.setValue('priority', 2);
        p.setValue('state', state);
        p.setValue('opened_at', dts(openedMs));
        p.setValue('sys_created_on', dts(openedMs));
        p.setValue('sys_updated_on', now.getValue());
        p.setValue('sys_created_by', 'opsintel_seed');
        p.setValue('sys_updated_by', 'opsintel_seed');
        p.setValue('correlation_id', TAG);
        return p.insert();
    }
    var vpnCis = P.network.cis.slice(0, 2);
    var vpnStart = ms('2026-07-01');
    var prbVpn = problem('VPN concentrator drops tunnels under peak load',
        'Recurring VPN disconnections since July 2026, concentrated on two VPN concentrators. Correlates with home-working peaks (Mon-Thu 08:00-10:00).',
        'Firmware defect in the VPN concentrator cluster exhausts session table under load; vendor bug confirmed, fixed in next maintenance release.',
        'Fail users over to secondary concentrator and clear stale sessions (see network runbook).',
        vpnCis.length ? vpnCis[0] : '', P.network.group, vpnStart + 20 * DAY, 104);
    var mailStart = ms('2026-09-08'), mailEnd = ms('2026-09-19');
    var prbMail = problem('Mail gateway rejecting external TLS connections',
        'Spike of email delivery incidents 8-19 Sep 2026 affecting Email and OWA users.',
        'Intermediate certificate missing from the mail gateway TLS chain after certificate renewal.',
        'Route affected partner domains via secondary gateway.',
        '', P.software.group, mailStart + 2 * DAY, 106);
    var posStart = ms('2025-11-20'), posEnd = ms('2025-12-03');

    // ------------------------------------------------------------------ incidents
    var hourWeights = [];
    for (var h = 0; h < 24; h++) hourWeights.push([h, (h >= 8 && h <= 17) ? (h === 9 || h === 14 ? 10 : 7) : (h >= 6 && h <= 20 ? 2 : 0.4)]);
    var counts = { total: 0, open: 0, breached: 0, vpn: 0, mail: 0, pos: 0, noService: 0, noCompany: 0 };
    var startMs = nowMs - DAYS * DAY;

    function create(kind, dayMs, opts) {
        var prof = P[kind];
        var sub = opts.sub || weighted(prof.subs);
        var openedMs = dayMs + weighted(hourWeights) * HOUR + Math.floor(rnd() * 60) * 60000;
        if (openedMs > nowMs - 10 * 60000) return;
        var impact = opts.impact || weighted([[1, 7], [2, 33], [3, 60]]);
        var urgency = opts.urgency || weighted([[1, 20], [2, 40], [3, 40]]);
        var prio = PRIO['' + impact + urgency];
        var hours = TARGET[prio] * lognormal(opts.mu !== undefined ? opts.mu : -0.85, 0.65);
        if (kind === 'inquiry') hours = hours * 0.5;
        var resolvedMs = openedMs + Math.max(0.1, hours) * HOUR;
        // Realistic backlog: some recent tickets are still being worked or waiting on someone.
        if (openedMs > nowMs - 21 * DAY && rnd() < 0.15) resolvedMs = nowMs + DAY;

        var inc = new GlideRecord('incident');
        inc.initialize();
        inc.setWorkflow(false);
        inc.autoSysFields(false);
        var caller = pick(callers);
        inc.setValue('caller_id', caller);
        inc.setValue('opened_by', rnd() < 0.6 ? caller : (deskUser.length ? deskUser[0] : caller));
        inc.setValue('contact_type', opts.contact || weighted(CONTACT));
        if (rnd() < 0.85 && companies.length) inc.setValue('company', pick(companies)); else counts.noCompany++;
        var svc = opts.service || (prof.services.length && rnd() < 0.9 ? pick(prof.services) : '');
        if (svc) inc.setValue('business_service', svc); else counts.noService++;
        var ci = opts.ci || (prof.cis.length && rnd() < 0.8 ? pick(prof.cis) : '');
        if (ci) inc.setValue('cmdb_ci', ci);
        inc.setValue('category', kind);
        sub = validSub(kind, sub);
        inc.setValue('subcategory', sub);
        inc.setValue('impact', impact);
        inc.setValue('urgency', urgency);
        inc.setValue('priority', prio);
        inc.setValue('assignment_group', prof.group);
        if (prof.members && prof.members.length) inc.setValue('assigned_to', pick(prof.members));
        var texts = (opts.text ? [opts.text] : (prof.text[sub] || ['Issue reported by user']));
        var shortText = pick(texts);
        inc.setValue('short_description', shortText);
        inc.setValue('description', shortText + '. Reported via ' + inc.getValue('contact_type') + '. Seeded by OpsIntel for analytics testing.');
        inc.setValue('opened_at', dts(openedMs));
        inc.setValue('sys_created_on', dts(openedMs));
        inc.setValue('sys_created_by', 'opsintel_seed');
        inc.setValue('sys_updated_by', 'opsintel_seed');
        inc.setValue('correlation_id', TAG);
        if (opts.problem) inc.setValue('problem_id', opts.problem);
        if (rnd() < 0.03) inc.setValue('reopen_count', 1);

        var state;
        if (resolvedMs <= nowMs) {
            var closedMs = resolvedMs + 3 * DAY;
            state = closedMs <= nowMs ? 7 : 6;
            inc.setValue('resolved_at', dts(resolvedMs));
            inc.setValue('resolved_by', inc.getValue('assigned_to') || inc.getValue('opened_by'));
            var code = opts.problem ? CLOSE.problem : (kind === 'inquiry' ? weighted([[CLOSE.solved, 6], [CLOSE.caller, 3], [CLOSE.user, 1]])
                : weighted([[CLOSE.solved, 6], [CLOSE.remote, 2], [CLOSE.workaround, 2]]));
            inc.setValue('close_code', code);
            inc.setValue('close_notes', opts.problem ? 'Workaround applied; linked to problem for permanent fix.' : 'Issue resolved and confirmed with caller.');
            if (state === 7) { inc.setValue('closed_at', dts(closedMs)); inc.setValue('closed_by', inc.getValue('resolved_by')); }
            inc.setValue('sys_updated_on', dts(state === 7 ? closedMs : resolvedMs));
            if (hours > TARGET[prio]) counts.breached++;
        } else {
            var ageH = (nowMs - openedMs) / HOUR;
            state = ageH < 4 ? 1 : (rnd() < 0.25 ? 3 : 2);
            if (state === 3) inc.setValue('hold_reason', 1);
            inc.setValue('sys_updated_on', dts(Math.min(nowMs, openedMs + ageH * 0.5 * HOUR)));
            counts.open++;
        }
        inc.setValue('state', state);
        inc.setValue('incident_state', state);
        inc.insert();
        counts.total++;
    }

    for (var d = 0; d <= DAYS; d++) {
        var dayMs = startMs + d * DAY;
        dayMs = dayMs - (dayMs % DAY);                      // midnight UTC
        var dow = dt(dayMs).getDayOfWeekUTC();              // 1 = Mon ... 7 = Sun
        var weekday = dow <= 5;
        var growth = 1 + 0.12 * (d / DAYS);
        var base = (weekday ? (dow === 1 ? 4.6 : 3.8) : 0.9) * growth;
        var n = poisson(base);
        for (var i = 0; i < n; i++) create(weighted(MIX), dayMs, {});
        // 1. VPN problem
        if (dayMs >= vpnStart && weekday) {
            var nv = poisson(1.1);
            for (var j = 0; j < nv; j++) {
                create('network', dayMs, { sub: 'vpn', problem: rnd() < 0.85 ? prbVpn : '', ci: vpnCis.length ? pick(vpnCis) : '',
                    service: P.network.services.length ? P.network.services[0] : '', impact: weighted([[2, 70], [1, 10], [3, 20]]),
                    urgency: weighted([[1, 30], [2, 60], [3, 10]]), mu: 0.05,
                    text: pick(['VPN tunnel drops every 10-15 minutes', 'Cannot stay connected to VPN during morning peak', 'VPN disconnects - session table full error'])});
                counts.vpn++;
            }
        }
        // 2. Mail gateway spike
        if (dayMs >= mailStart && dayMs <= mailEnd) {
            var nm = poisson(weekday ? 7 : 2);
            var mailSvcs = byName('cmdb_ci_service', ['Email', 'Outlook Web Access (OWA)']);
            for (var m = 0; m < nm; m++) {
                create('software', dayMs, { sub: 'email', problem: rnd() < 0.7 ? prbMail : '', service: mailSvcs.length ? pick(mailSvcs) : '',
                    mu: -0.35, text: pick(['External emails bouncing with TLS handshake error', 'Partners report our emails are rejected', 'Emails to customers stuck in queue'])});
                counts.mail++;
            }
        }
        // 3. Retail POS peak
        if (dayMs >= posStart && dayMs <= posEnd) {
            var np = poisson(3);
            var posSvc = byName('cmdb_ci_service', ['Retail POS (Point of Sale)']);
            for (var q = 0; q < np; q++) {
                create('hardware', dayMs, { sub: pick(['keyboard', 'cpu', 'monitor']), service: posSvc.length ? posSvc[0] : '',
                    urgency: weighted([[1, 40], [2, 50], [3, 10]]), text: pick(['POS till frozen during peak trading', 'Card reader on POS terminal not responding', 'POS receipt printer jammed repeatedly'])});
                counts.pos++;
            }
        }
    }

    gs.print('OpsIntel seed complete: ' + JSON.stringify(counts));
    gs.print('Problems: VPN ' + prbVpn + ', Mail ' + prbMail + '. Remove with remove_seed.js (correlation_id = ' + TAG + ').');
})();
