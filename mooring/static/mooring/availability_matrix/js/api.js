// Thin fetch() wrapper for the Availability Matrix API endpoints.
window.AvailabilityMatrixAPI = (function () {
    var treeAbortController = null;
    var cellsAbortController = null;

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
        var controller = new AbortController();
        cellsAbortController = controller;

        var query = new URLSearchParams();
        query.set('site_ids', (params.siteIds || []).join(','));
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
            .finally(function () {
                // Only clear the shared reference if a newer request hasn't already replaced it
                if (cellsAbortController === controller) {
                    cellsAbortController = null;
                }
            });
    }

    return {
        fetchTree: fetchTree,
        fetchCells: fetchCells
    };
})();

