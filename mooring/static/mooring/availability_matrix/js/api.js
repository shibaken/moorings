// Thin fetch() wrapper for the Availability Matrix API endpoints.
window.AvailabilityMatrixAPI = (function () {
    var treeAbortController = null;

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

    return {
        fetchTree: fetchTree
    };
})();
