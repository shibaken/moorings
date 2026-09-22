// Coloured availability cell grid rendered in g.matrix-cells. Requires window.d3, MooringTree, MooringTimeline, and AvailabilityMatrixAPI.
window.MooringMatrix = (function () {
    var ROW_HEIGHT = 24; // must match tree.js

    var currentRange = null;
    var debounceTimer = null;

    function siteRowsFromTree() {
        var rows = (window.MooringTree && typeof window.MooringTree.getVisibleRows === 'function')
            ? window.MooringTree.getVisibleRows()
            : [];
        var siteEntries = [];
        rows.forEach(function (row, index) {
            if (row.type === 'site') {
                siteEntries.push({ row: row, index: index });
            }
        });
        return siteEntries;
    }

    function formatDate(date) {
        return d3.timeFormat('%Y-%m-%d')(date);
    }

    function scheduleRender() {
        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }
        debounceTimer = setTimeout(fetchAndRender, 150);
    }

    function fetchAndRender() {
        if (!currentRange || !window.MooringTimeline) {
            return;
        }

        var siteEntries = siteRowsFromTree();
        var siteIds = siteEntries.map(function (entry) { return entry.row.id; });

        if (siteIds.length === 0) {
            render([], siteEntries);
            return;
        }

        window.AvailabilityMatrixAPI.fetchCells({
            siteIds: siteIds,
            startDate: formatDate(currentRange.startDate),
            endDate: formatDate(currentRange.endDate)
        }).then(function (cells) {
            render(cells, siteEntries);
        }).catch(function (error) {
            if (error.name === 'AbortError') {
                // Expected when a newer request supersedes this one; not a real failure
                return;
            }
            console.error('Availability matrix cells load failed:', error);
        });
    }

    function render(cells, siteEntries) {
        var columnScale = window.MooringTimeline.getColumnScale();
        var columns = window.MooringTimeline.getColumns();
        var layout = window.MooringTimeline.getLayout();
        if (!columnScale || !layout) {
            return;
        }

        var cellLookup = {};
        cells.forEach(function (cell) {
            cellLookup[cell.site_id + ':' + cell.date] = cell;
        });

        var cellData = [];
        siteEntries.forEach(function (entry) {
            columns.forEach(function (columnDate) {
                var dateKey = formatDate(columnDate);
                var cell = cellLookup[entry.row.id + ':' + dateKey];
                cellData.push({
                    key: entry.row.id + ':' + dateKey,
                    rowIndex: entry.index,
                    columnDate: columnDate,
                    status: cell ? cell.status : 'no-data',
                    rate: cell ? cell.rate : null
                });
            });
        });

        var svg = d3.select('#matrix-svg');
        var g = svg.select('g.matrix-cells');
        if (g.empty()) {
            g = svg.append('g').attr('class', 'matrix-cells');
        }
        g.attr('transform', 'translate(' + layout.rowLabelWidth + ',' + layout.headerHeight + ')');

        var cellSelection = g.selectAll('rect.avm-cell')
            .data(cellData, function (d) { return d.key; });

        cellSelection.exit().remove();

        var cellEnter = cellSelection.enter()
            .append('rect');

        var cellMerge = cellEnter.merge(cellSelection);

        cellMerge
            .attr('class', function (d) { return 'avm-cell avm-cell-' + d.status; })
            .attr('x', function (d) { return columnScale(d.columnDate.toISOString()); })
            .attr('y', function (d) { return d.rowIndex * ROW_HEIGHT; })
            .attr('width', columnScale.bandwidth())
            .attr('height', ROW_HEIGHT);
    }

    function init() {
        document.addEventListener('matrix:range-changed', function (event) {
            currentRange = event.detail;
            scheduleRender();
        });
        document.addEventListener('tree:visible-rows-changed', function () {
            scheduleRender();
        });
    }

    return {
        init: init
    };
})();
