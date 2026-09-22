// Left-axis MooringArea / Mooringsite tree rendered in g.axis-left. Requires window.d3 and window.AvailabilityMatrixAPI.
window.MooringTree = (function () {
    var ROW_HEIGHT = 24;
    var INDENT_WIDTH = 16;
    var ROW_WIDTH = 240;
    var HEADER_HEIGHT = 40; // reserved for the timeline header rendered by timeline.js above the rows
    var SEARCH_DEBOUNCE_MS = 300;

    var areas = [];
    var visibleRows = [];
    var collapsedAreaIds = {};

    var baseParams = {};
    var currentSearch = '';
    var currentPage = 1;
    var currentPageSize = 30;
    var pageInfo = { count: 0, totalPages: 0 };
    var searchDebounceTimer = null;

    function flattenTree() {
        var flat = [];
        areas.forEach(function (area) {
            flat.push({
                type: 'area',
                id: area.id,
                name: area.name,
                isOpen: area.is_open,
                depth: 0,
                parentId: null
            });
            if (!collapsedAreaIds[area.id]) {
                (area.sites || []).forEach(function (site) {
                    flat.push({
                        type: 'site',
                        id: site.id,
                        name: site.name,
                        isOpen: site.is_open,
                        depth: 1,
                        parentId: area.id
                    });
                });
            }
        });
        return flat;
    }

    function toggleArea(areaId) {
        collapsedAreaIds[areaId] = !collapsedAreaIds[areaId];
        render();
    }

    function render() {
        visibleRows = flattenTree();

        var svg = d3.select('#matrix-svg');
        var layer = svg.select('g.axis-left');
        if (layer.empty()) {
            layer = svg.append('g').attr('class', 'axis-left');
        }

        var rowSelection = layer.selectAll('g.avm-row')
            .data(visibleRows, function (d) { return d.type + ':' + d.id; });

        rowSelection.exit().remove();

        var rowEnter = rowSelection.enter()
            .append('g')
            .attr('class', function (d) { return 'avm-row avm-row-' + d.type; })
            .style('cursor', function (d) { return d.type === 'area' ? 'pointer' : 'default'; })
            .on('click', function (event, d) {
                if (d.type === 'area') {
                    toggleArea(d.id);
                }
            });

        rowEnter.append('rect').attr('class', 'avm-row-bg');
        rowEnter.append('text').attr('class', 'avm-row-chevron');
        rowEnter.append('text').attr('class', 'avm-row-label');

        var rowMerge = rowEnter.merge(rowSelection);

        rowMerge
            .attr('transform', function (d, i) { return 'translate(0,' + (HEADER_HEIGHT + i * ROW_HEIGHT) + ')'; })
            .classed('avm-row-closed', function (d) { return !d.isOpen; });

        rowMerge.select('rect.avm-row-bg')
            .attr('width', ROW_WIDTH)
            .attr('height', ROW_HEIGHT);

        rowMerge.select('text.avm-row-chevron')
            .attr('x', function (d) { return d.depth * INDENT_WIDTH + 4; })
            .attr('y', ROW_HEIGHT / 2)
            .text(function (d) {
                if (d.type !== 'area') {
                    return '';
                }
                return collapsedAreaIds[d.id] ? '\u25B6' : '\u25BC';
            });

        rowMerge.select('text.avm-row-label')
            .attr('x', function (d) { return d.depth * INDENT_WIDTH + 18; })
            .attr('y', ROW_HEIGHT / 2)
            .text(function (d) { return d.name; });

        var currentWidth = parseInt(svg.attr('width'), 10) || ROW_WIDTH;
        svg.attr('width', currentWidth);
        svg.attr('height', HEADER_HEIGHT + Math.max(visibleRows.length, 1) * ROW_HEIGHT);

        document.dispatchEvent(new CustomEvent('tree:visible-rows-changed', {
            detail: { rows: getVisibleRows() }
        }));
    }

    function renderPaginationControls() {
        var pageInput = document.getElementById('avm-search-input');
        if (pageInput && pageInput.value !== currentSearch) {
            pageInput.value = currentSearch;
        }

        var pageSizeSelect = document.getElementById('avm-page-size');
        if (pageSizeSelect && pageSizeSelect.value !== String(currentPageSize)) {
            pageSizeSelect.value = String(currentPageSize);
        }

        var prevButton = document.getElementById('avm-prev-page');
        if (prevButton) {
            prevButton.disabled = currentPage <= 1;
        }

        var nextButton = document.getElementById('avm-next-page');
        if (nextButton) {
            nextButton.disabled = currentPage >= pageInfo.totalPages;
        }

        var infoLabel = document.getElementById('avm-page-info');
        if (infoLabel) {
            infoLabel.textContent = 'Page ' + currentPage + ' of ' + Math.max(pageInfo.totalPages, 1) +
                ' (' + pageInfo.count + ' moorings)';
        }
    }

    function fetchAndRender() {
        var params = Object.assign({}, baseParams, {
            search: currentSearch,
            page: currentPage,
            page_size: currentPageSize
        });

        return window.AvailabilityMatrixAPI.fetchTree(params).then(function (data) {
            areas = data.results || [];
            pageInfo = { count: data.count, totalPages: data.total_pages };
            currentPage = data.current_page;
            currentPageSize = data.page_size;
            renderPaginationControls();
            render();
        });
    }

    function goToPage(page) {
        if (page < 1 || (pageInfo.totalPages && page > pageInfo.totalPages)) {
            return;
        }
        currentPage = page;
        fetchAndRender();
    }

    function setSearch(value) {
        currentSearch = value;
        currentPage = 1;
        fetchAndRender();
    }

    function setPageSize(pageSize) {
        currentPageSize = pageSize;
        currentPage = 1;
        fetchAndRender();
    }

    function bindControls() {
        var searchInput = document.getElementById('avm-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', function (event) {
                var value = event.target.value;
                if (searchDebounceTimer) {
                    clearTimeout(searchDebounceTimer);
                }
                searchDebounceTimer = setTimeout(function () {
                    setSearch(value);
                }, SEARCH_DEBOUNCE_MS);
            });
        }

        var prevButton = document.getElementById('avm-prev-page');
        if (prevButton) {
            prevButton.addEventListener('click', function () {
                goToPage(currentPage - 1);
            });
        }

        var nextButton = document.getElementById('avm-next-page');
        if (nextButton) {
            nextButton.addEventListener('click', function () {
                goToPage(currentPage + 1);
            });
        }

        var pageSizeSelect = document.getElementById('avm-page-size');
        if (pageSizeSelect) {
            pageSizeSelect.addEventListener('change', function (event) {
                setPageSize(parseInt(event.target.value, 10));
            });
        }
    }

    function init(options) {
        options = options || {};
        baseParams = {
            park: options.park,
            mooring_group: options.mooringGroup
        };
        bindControls();
        return fetchAndRender();
    }

    function getVisibleRows() {
        return visibleRows.slice();
    }

    return {
        init: init,
        getVisibleRows: getVisibleRows
    };
})();
