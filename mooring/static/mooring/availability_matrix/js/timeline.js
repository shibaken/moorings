// Top-axis calendar timeline rendered in g.axis-top, with prev/next/today navigation. Requires window.d3.
window.MooringTimeline = (function () {
    var HEADER_HEIGHT = 40;
    var ROW_LABEL_WIDTH = 240; // must match tree.js ROW_WIDTH so axes align

    var COLUMN_WIDTH = { day: 28, week: 50, month: 70 };
    var PAGE_SIZE = { day: 30, week: 26, month: 12 };

    var granularity = 'day';
    var startDate = null; // set lazily in init(), once d3 is guaranteed to be loaded
    var columns = [];
    var columnScale = null;

    function stepFnFor(gran) {
        if (gran === 'week') {
            return d3.timeWeek;
        }
        if (gran === 'month') {
            return d3.timeMonth;
        }
        return d3.timeDay;
    }

    function pageStart(date, gran) {
        return stepFnFor(gran).floor(date);
    }

    function buildColumns() {
        var pageSize = PAGE_SIZE[granularity];
        var stepFn = stepFnFor(granularity);
        var stopBoundary = stepFn.offset(startDate, pageSize);
        columns = stepFn.range(startDate, stopBoundary);

        var columnWidth = COLUMN_WIDTH[granularity];
        columnScale = d3.scaleBand()
            .domain(columns.map(function (d) { return d.toISOString(); }))
            .range([0, columns.length * columnWidth]);

        return {
            startDate: startDate,
            endDate: d3.timeDay.offset(stopBoundary, -1),
            columnWidth: columnWidth
        };
    }

    function formatLabel(date) {
        if (granularity === 'week') {
            return d3.timeFormat('%d/%m')(date);
        }
        if (granularity === 'month') {
            return d3.timeFormat('%b %Y')(date);
        }
        return d3.timeFormat('%a %d')(date);
    }

    function isWeekend(date) {
        var day = date.getDay(); // 0 = Sunday, 6 = Saturday
        return day === 0 || day === 6;
    }

    function updateDateLabel(range) {
        var labelEl = document.getElementById('avm-date-label');
        if (!labelEl) {
            return;
        }
        var formatFull = d3.timeFormat('%d/%m/%Y');
        labelEl.textContent = formatFull(range.startDate) + ' \u2013 ' + formatFull(range.endDate);
    }

    function emitRangeChanged(range) {
        var event = new CustomEvent('matrix:range-changed', {
            detail: {
                startDate: range.startDate,
                endDate: range.endDate,
                granularity: granularity
            }
        });
        document.dispatchEvent(event);
    }

    function render() {
        var range = buildColumns();
        var columnWidth = range.columnWidth;

        var svg = d3.select('#matrix-svg');
        var layer = svg.select('g.axis-top');
        if (layer.empty()) {
            layer = svg.append('g').attr('class', 'axis-top');
        }
        layer.attr('transform', 'translate(' + ROW_LABEL_WIDTH + ',0)');

        var colSelection = layer.selectAll('g.avm-col')
            .data(columns, function (d) { return d.toISOString(); });

        colSelection.exit().remove();

        var colEnter = colSelection.enter()
            .append('g')
            .attr('class', 'avm-col');

        colEnter.append('rect').attr('class', 'avm-col-bg');
        colEnter.append('line').attr('class', 'avm-col-gridline');
        colEnter.append('text').attr('class', 'avm-col-label');

        var colMerge = colEnter.merge(colSelection);

        colMerge
            .attr('transform', function (d) { return 'translate(' + columnScale(d.toISOString()) + ',0)'; })
            .classed('avm-col-weekend', function (d) { return granularity === 'day' && isWeekend(d); });

        colMerge.select('rect.avm-col-bg')
            .attr('width', columnWidth)
            .attr('height', HEADER_HEIGHT);

        colMerge.select('line.avm-col-gridline')
            .attr('x1', columnWidth)
            .attr('x2', columnWidth)
            .attr('y1', 0)
            .attr('y2', HEADER_HEIGHT);

        colMerge.select('text.avm-col-label')
            .attr('x', columnWidth / 2)
            .attr('y', HEADER_HEIGHT / 2)
            .text(formatLabel);

        var currentHeight = parseInt(svg.attr('height'), 10) || HEADER_HEIGHT;
        svg.attr('width', ROW_LABEL_WIDTH + columns.length * columnWidth);
        svg.attr('height', currentHeight);

        updateDateLabel(range);
        emitRangeChanged(range);
    }

    function shiftPage(direction) {
        var pageSize = PAGE_SIZE[granularity];
        startDate = stepFnFor(granularity).offset(startDate, direction * pageSize);
        render();
    }

    function goToday() {
        startDate = pageStart(new Date(), granularity);
        render();
    }

    function setGranularity(newGranularity) {
        if (!COLUMN_WIDTH.hasOwnProperty(newGranularity) || newGranularity === granularity) {
            return;
        }
        startDate = pageStart(startDate, newGranularity);
        granularity = newGranularity;
        render();
    }

    function bindControls() {
        var granularitySelect = document.getElementById('avm-granularity');
        var prevButton = document.getElementById('avm-prev');
        var nextButton = document.getElementById('avm-next');
        var todayButton = document.getElementById('avm-today');

        if (granularitySelect) {
            granularitySelect.value = granularity;
            granularitySelect.addEventListener('change', function (event) {
                setGranularity(event.target.value);
            });
        }
        if (prevButton) {
            prevButton.addEventListener('click', function () { shiftPage(-1); });
        }
        if (nextButton) {
            nextButton.addEventListener('click', function () { shiftPage(1); });
        }
        if (todayButton) {
            todayButton.addEventListener('click', goToday);
        }
    }

    function init() {
        if (startDate === null) {
            startDate = d3.timeDay.floor(new Date());
        }
        bindControls();
        render();
    }

    function getColumnScale() {
        return columnScale;
    }

    function getColumns() {
        return columns.slice();
    }

    function getLayout() {
        return {
            rowLabelWidth: ROW_LABEL_WIDTH,
            headerHeight: HEADER_HEIGHT,
            columnWidth: COLUMN_WIDTH[granularity],
            granularity: granularity
        };
    }

    return {
        init: init,
        getColumnScale: getColumnScale,
        getColumns: getColumns,
        getLayout: getLayout
    };
})();
