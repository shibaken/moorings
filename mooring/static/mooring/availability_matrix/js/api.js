// Thin fetch() wrapper for the Availability Matrix API endpoints.
window.AvailabilityMatrixAPI = (function () {
    var treeAbortController = null;
    var cellsAbortController = null;
    var cellDetailAbortController = null;

    // Simple session-lifetime caches keyed by request parameters, per plan §Phase 5 performance notes.
    var cellsCache = new Map();
    var cellDetailCache = new Map();

    function cellsCacheKey(siteIds, startDate, endDate) {
        return siteIds.slice().sort(function (a, b) { return a - b; }).join(',') + '|' + startDate + '|' + endDate;
    }

    function cellDetailCacheKey(siteId, dateStr) {
        return siteId + '|' + dateStr;
    }

    function fetchTree(params) {
        if (treeAbortController) {
            treeAbortController.abort();
        }
        treeAbortController = new AbortController();

        var query = new URLSearchParams();
        if (params && params.park) {
            query.set('park', params.park);
        }
        if (params && params.mooring_group) {
            query.set('mooring_group', params.mooring_group);
        }

        var url = '/api/availability-matrix/tree/';
        var queryString = query.toString();
        if (queryString) {
            url += '?' + queryString;
        }

        return fetch(url, { signal: treeAbortController.signal, credentials: 'same-origin' })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Failed to fetch availability matrix tree: ' + response.status);
                }
                return response.json();
            });
    }

    function fetchCells(params) {
        if (cellsAbortController) {
            cellsAbortController.abort();
        }

        var siteIds = params.siteIds || [];
        var cacheKey = cellsCacheKey(siteIds, params.startDate, params.endDate);
        if (cellsCache.has(cacheKey)) {
            return Promise.resolve(cellsCache.get(cacheKey));
        }

        var controller = new AbortController();
        cellsAbortController = controller;

        var query = new URLSearchParams();
        query.set('site_ids', siteIds.join(','));
        query.set('start_date', params.startDate);
        query.set('end_date', params.endDate);

        var url = '/api/availability-matrix/cells/?' + query.toString();

        return fetch(url, { signal: controller.signal, credentials: 'same-origin' })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Failed to fetch availability matrix cells: ' + response.status);
                }
                return response.json();
            })
            .then(function (data) {
                cellsCache.set(cacheKey, data);
                return data;
            })
            .finally(function () {
                // Only clear the shared reference if a newer request hasn't already replaced it
                if (cellsAbortController === controller) {
                    cellsAbortController = null;
                }
            });
    }

    function fetchCellDetail(siteId, dateStr) {
        var cacheKey = cellDetailCacheKey(siteId, dateStr);
        if (cellDetailCache.has(cacheKey)) {
            return Promise.resolve(cellDetailCache.get(cacheKey));
        }

        if (cellDetailAbortController) {
            cellDetailAbortController.abort();
        }
        var controller = new AbortController();
        cellDetailAbortController = controller;

        var query = new URLSearchParams();
        query.set('site_id', siteId);
        query.set('date', dateStr);

        var url = '/api/availability-matrix/cell-detail/?' + query.toString();

        return fetch(url, { signal: controller.signal, credentials: 'same-origin' })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Failed to fetch availability matrix cell detail: ' + response.status);
                }
                return response.json();
            })
            .then(function (data) {
                cellDetailCache.set(cacheKey, data);
                return data;
            })
            .finally(function () {
                if (cellDetailAbortController === controller) {
                    cellDetailAbortController = null;
                }
            });
    }

    return {
        fetchTree: fetchTree,
        fetchCells: fetchCells,
        fetchCellDetail: fetchCellDetail
    };
})();


