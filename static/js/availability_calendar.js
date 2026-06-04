/**
 * Availability Calendar Component
 *
 * renderCalendar(containerId, availableDays, bookedDates, closedDates, mode, callback)
 *
 * @param {string}   containerId   - ID of the DOM element to render into
 * @param {number[]} availableDays - Weekday indices available: 0=Mon … 6=Sun
 * @param {string[]} bookedDates   - 'YYYY-MM-DD' strings blocked by approved bookings (shown red)
 * @param {string[]} closedDates   - 'YYYY-MM-DD' strings manually closed by university (shown grey)
 * @param {string}   mode          - 'display' | 'multiselect'
 * @param {Function} callback      - In multiselect mode: called as callback(selectedDateArray) on change
 */
function renderCalendar(containerId, availableDays, bookedDates, closedDates, mode, callback) {
    const container = document.getElementById(containerId);
    if (!container) return;

    injectCalendarStyles();

    const bookedSet = new Set(bookedDates);
    const closedSet = new Set(closedDates);
    const todayDate = new Date();
    todayDate.setHours(0, 0, 0, 0);

    let viewYear = todayDate.getFullYear();
    let viewMonth = todayDate.getMonth();
    let selectedDates = new Set(); // for multiselect mode

    const MONTH_NAMES = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
    const DAY_HEADERS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];

    function toDateStr(d) {
        return d.getFullYear() + '-' +
            String(d.getMonth() + 1).padStart(2, '0') + '-' +
            String(d.getDate()).padStart(2, '0');
    }

    // JS getDay(): 0=Sun … 6=Sat → our convention: 0=Mon … 6=Sun
    function jsToOurDow(jsDay) { return (jsDay + 6) % 7; }
    function isDayOpen(jsDay) { return availableDays.includes(jsToOurDow(jsDay)); }

    function getDateStatus(dateStr, jsDay) {
        const d = new Date(dateStr + 'T00:00:00');
        if (d < todayDate) return 'past';
        if (bookedSet.has(dateStr)) return 'booked';
        if (closedSet.has(dateStr)) return 'closed';
        if (!isDayOpen(jsDay)) return 'closed';
        return 'open';
    }

    function render() {
        const firstDay = new Date(viewYear, viewMonth, 1);
        const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
        const startOffset = (firstDay.getDay() + 6) % 7; // Mon-first offset

        let html = `<div class="avail-cal">
            <div class="avail-cal-header">
                <button type="button" class="avail-cal-nav" id="${containerId}-prev">&#8249;</button>
                <span class="avail-cal-month">${MONTH_NAMES[viewMonth]} ${viewYear}</span>
                <button type="button" class="avail-cal-nav" id="${containerId}-next">&#8250;</button>
            </div>
            <table class="avail-cal-table"><thead><tr>`;
        DAY_HEADERS.forEach(h => { html += `<th>${h}</th>`; });
        html += `</tr></thead><tbody><tr>`;

        let cellCount = 0;
        for (let i = 0; i < startOffset; i++) { html += `<td></td>`; cellCount++; }

        for (let day = 1; day <= daysInMonth; day++) {
            if (cellCount % 7 === 0 && cellCount > 0) html += `</tr><tr>`;

            const d = new Date(viewYear, viewMonth, day);
            const dateStr = toDateStr(d);
            const status = getDateStatus(dateStr, d.getDay());
            const isSelected = selectedDates.has(dateStr);

            let cls = 'avail-day';
            if (isSelected)          cls += ' avail-selected';
            else if (status === 'past')   cls += ' avail-past';
            else if (status === 'booked') cls += ' avail-booked';
            else if (status === 'closed') cls += ' avail-closed';
            else                          cls += ' avail-open';

            const clickable = mode === 'multiselect' && status === 'open';
            html += `<td class="${cls}"${clickable ? ` data-date="${dateStr}"` : ''}>${day}</td>`;
            cellCount++;
        }
        while (cellCount % 7 !== 0) { html += `<td></td>`; cellCount++; }
        html += `</tr></tbody></table>`;

        if (mode === 'multiselect') {
            const count = selectedDates.size;
            const summary = count === 0
                ? '<span style="color:#999;">Click available dates to select them</span>'
                : `<strong>${count} date${count !== 1 ? 's' : ''} selected</strong>`;
            html += `<div class="avail-cal-summary">${summary}</div>`;
        } else {
            html += `<div class="avail-cal-legend">
                <span class="legend-item"><span class="ls-open"></span>Available</span>
                <span class="legend-item"><span class="ls-booked"></span>Booked</span>
                <span class="legend-item"><span class="ls-closed"></span>Closed</span>
            </div>`;
        }

        html += `</div>`;
        container.innerHTML = html;

        document.getElementById(`${containerId}-prev`).addEventListener('click', () => {
            viewMonth--;
            if (viewMonth < 0) { viewMonth = 11; viewYear--; }
            render();
        });
        document.getElementById(`${containerId}-next`).addEventListener('click', () => {
            viewMonth++;
            if (viewMonth > 11) { viewMonth = 0; viewYear++; }
            render();
        });

        if (mode === 'multiselect') {
            container.querySelectorAll('td[data-date]').forEach(cell => {
                cell.addEventListener('click', () => {
                    const d = cell.getAttribute('data-date');
                    if (selectedDates.has(d)) { selectedDates.delete(d); }
                    else { selectedDates.add(d); }
                    if (callback) callback(Array.from(selectedDates).sort());
                    render();
                });
            });
        }
    }

    render();
}

function injectCalendarStyles() {
    if (document.getElementById('avail-cal-styles')) return;
    const style = document.createElement('style');
    style.id = 'avail-cal-styles';
    style.textContent = `
        .avail-cal { font-family: 'Poppins', sans-serif; width: 100%; max-width: 280px; }
        .avail-cal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
        .avail-cal-nav { background: none; border: none; font-size: 1.6rem; line-height: 1; cursor: pointer; color: #9e7a10; padding: 0 4px; }
        .avail-cal-nav:hover { color: #f0b429; }
        .avail-cal-month { font-weight: 700; color: #f0b429; font-size: 0.95rem; }
        .avail-cal-table { width: 100%; border-collapse: collapse; }
        .avail-cal-table th { text-align: center; padding: 3px 1px; font-size: 0.75rem; color: #c890ff; font-weight: 600; }
        .avail-cal-table td { text-align: center; padding: 5px 2px; font-size: 0.85rem; cursor: default; border-radius: 4px; }
        .avail-open   { background: rgba(240,180,41,0.12); color: #f0b429; cursor: pointer; }
        .avail-open:hover { background: #9e7a10; color: #07080b; }
        .avail-booked { background: rgba(248,113,113,0.12); color: #f87171; text-decoration: line-through; }
        .avail-closed { color: #38384e; }
        .avail-past   { color: #252636; }
        .avail-selected { background: #f0b429 !important; color: #07080b !important; cursor: pointer; border-radius: 4px; }
        .avail-cal-summary { margin-top: 8px; font-size: 0.82rem; color: #8888a0; text-align: center; min-height: 1.2em; }
        .avail-cal-legend { margin-top: 8px; display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; font-size: 0.78rem; color: #8888a0; }
        .legend-item { display: flex; align-items: center; gap: 4px; }
        .ls-open   { display: inline-block; width: 12px; height: 12px; background: rgba(240,180,41,0.25); border-radius: 3px; }
        .ls-booked { display: inline-block; width: 12px; height: 12px; background: rgba(248,113,113,0.25); border-radius: 3px; }
        .ls-closed { display: inline-block; width: 12px; height: 12px; background: #1a1b28; border-radius: 3px; }
    `;
    document.head.appendChild(style);
}
