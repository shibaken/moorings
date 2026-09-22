// Hover tooltip + click detail popup for matrix cells. Requires window.d3 and AvailabilityMatrixAPI.
window.MooringInteractions = (function () {
    var STATUS_LABELS = {
        open: 'Open',
        closed: 'Closed',
        partial: 'Partial',
        'no-data': 'No data'
    };

    var tooltipEl = null;
    var modalBackdropEl = null;
    var modalEl = null;

    function ensureTooltip() {
        if (tooltipEl) {
            return tooltipEl;
        }
        var root = document.getElementById('matrix-root');
        tooltipEl = document.createElement('div');
        tooltipEl.className = 'avm-tooltip';
        tooltipEl.style.display = 'none';
        root.appendChild(tooltipEl);
        return tooltipEl;
    }

    function ensureModal() {
        if (modalEl) {
            return;
        }
        var root = document.getElementById('matrix-root');

        modalBackdropEl = document.createElement('div');
        modalBackdropEl.className = 'avm-modal-backdrop';
        modalBackdropEl.style.display = 'none';
        modalBackdropEl.addEventListener('click', function (event) {
            if (event.target === modalBackdropEl) {
                closeModal();
            }
        });

        modalEl = document.createElement('div');
        modalEl.className = 'avm-modal';
        modalBackdropEl.appendChild(modalEl);

        root.appendChild(modalBackdropEl);

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closeModal();
            }
        });
    }

    function showTooltip(event, cellDatum) {
        var tooltip = ensureTooltip();
        var statusLabel = STATUS_LABELS[cellDatum.status] || cellDatum.status;

        tooltip.innerHTML =
            '<div class="avm-tooltip-site">' + cellDatum.siteName + '</div>' +
            '<div class="avm-tooltip-date">' + cellDatum.dateLabel + '</div>' +
            '<div class="avm-tooltip-status">' + statusLabel + '</div>' +
            '<div class="avm-tooltip-rate">' + (cellDatum.rate !== null && cellDatum.rate !== undefined ? cellDatum.rate : '') + '</div>';

        positionTooltip(event);
        tooltip.style.display = 'block';
    }

    function positionTooltip(event) {
        if (!tooltipEl) {
            return;
        }
        var root = document.getElementById('matrix-root');
        var rootRect = root.getBoundingClientRect();
        tooltipEl.style.left = (event.clientX - rootRect.left + 12) + 'px';
        tooltipEl.style.top = (event.clientY - rootRect.top + 12) + 'px';
    }

    function hideTooltip() {
        if (tooltipEl) {
            tooltipEl.style.display = 'none';
        }
    }

    function formatTime(timeStr) {
        if (!timeStr) {
            return '&ndash;';
        }
        return timeStr.slice(0, 5);
    }

    function renderModalContent(detail) {
        var html = '<div class="avm-modal-header">' +
            '<span class="avm-modal-title">' + detail.site_name + ' (' + detail.mooringarea_name + ')</span>' +
            '<span class="avm-modal-date">' + detail.date + '</span>' +
            '<button type="button" class="avm-modal-close" aria-label="Close">&times;</button>' +
            '</div>';

        html += '<div class="avm-modal-body">';

        html += '<h4>Rate</h4>';
        if (detail.rate) {
            html += '<table class="avm-modal-table">' +
                '<tr><td>Price model</td><td>' + detail.rate.price_model + '</td></tr>' +
                '<tr><td>Rate type</td><td>' + detail.rate.rate_type + '</td></tr>' +
                '<tr><td>Mooring</td><td>$' + detail.rate.mooring + '</td></tr>' +
                '<tr><td>Adult</td><td>' + (detail.rate.adult !== null ? '$' + detail.rate.adult : '&ndash;') + '</td></tr>' +
                '<tr><td>Concession</td><td>' + (detail.rate.concession !== null ? '$' + detail.rate.concession : '&ndash;') + '</td></tr>' +
                '<tr><td>Child</td><td>' + (detail.rate.child !== null ? '$' + detail.rate.child : '&ndash;') + '</td></tr>' +
                '<tr><td>Infant</td><td>' + (detail.rate.infant !== null ? '$' + detail.rate.infant : '&ndash;') + '</td></tr>' +
                '<tr><td>Reason</td><td>' + (detail.rate.reason || '&ndash;') + '</td></tr>' +
                '<tr><td>Details</td><td>' + (detail.rate.details || '&ndash;') + '</td></tr>' +
                '</table>';
        } else {
            html += '<p>No rate resolved for this date.</p>';
        }

        html += '<h4>Booking periods</h4>';
        if (detail.booking_periods.length > 0) {
            html += '<table class="avm-modal-table avm-modal-periods">' +
                '<thead><tr><th>Name</th><th>Start</th><th>Finish</th><th>Small</th><th>Medium</th><th>Large</th><th>Status</th></tr></thead><tbody>';
            detail.booking_periods.forEach(function (bp) {
                html += '<tr class="avm-period-' + bp.status + '">' +
                    '<td>' + bp.name + '</td>' +
                    '<td>' + formatTime(bp.start_time) + '</td>' +
                    '<td>' + formatTime(bp.finish_time) + '</td>' +
                    '<td>' + (bp.small_price !== null ? '$' + bp.small_price : '&ndash;') + '</td>' +
                    '<td>' + (bp.medium_price !== null ? '$' + bp.medium_price : '&ndash;') + '</td>' +
                    '<td>' + (bp.large_price !== null ? '$' + bp.large_price : '&ndash;') + '</td>' +
                    '<td>' + (bp.status === 'open' ? 'Open' : 'Closed') + '</td>' +
                    '</tr>';
            });
            html += '</tbody></table>';
        } else {
            html += '<p>No booking periods resolved for this date.</p>';
        }

        html += '<h4>Existing bookings</h4>';
        if (detail.bookings.length > 0) {
            html += '<ul class="avm-modal-bookings">';
            detail.bookings.forEach(function (booking) {
                html += '<li>#' + booking.id + ' &ndash; ' + booking.booking_type +
                    ' (' + booking.from_dt + ' to ' + booking.to_dt + ')</li>';
            });
            html += '</ul>';
        } else {
            html += '<p>No existing bookings for this site/date.</p>';
        }

        html += '</div>';

        modalEl.innerHTML = html;
        modalEl.querySelector('.avm-modal-close').addEventListener('click', closeModal);
    }

    function openModal(siteId, dateStr) {
        ensureModal();
        modalEl.innerHTML = '<div class="avm-modal-header"><span class="avm-modal-title">Loading&hellip;</span></div>';
        modalBackdropEl.style.display = 'flex';

        window.AvailabilityMatrixAPI.fetchCellDetail(siteId, dateStr).then(function (detail) {
            renderModalContent(detail);
        }).catch(function (error) {
            if (error.name === 'AbortError') {
                return;
            }
            modalEl.innerHTML = '<div class="avm-modal-header"><span class="avm-modal-title">Failed to load details</span>' +
                '<button type="button" class="avm-modal-close" aria-label="Close">&times;</button></div>' +
                '<div class="avm-modal-body"><p>' + error.message + '</p></div>';
            modalEl.querySelector('.avm-modal-close').addEventListener('click', closeModal);
            console.error('Availability matrix cell detail load failed:', error);
        });
    }

    function closeModal() {
        if (modalBackdropEl) {
            modalBackdropEl.style.display = 'none';
        }
    }

    function init() {
        ensureTooltip();
        ensureModal();
    }

    return {
        init: init,
        showTooltip: showTooltip,
        positionTooltip: positionTooltip,
        hideTooltip: hideTooltip,
        openModal: openModal,
        closeModal: closeModal
    };
})();
