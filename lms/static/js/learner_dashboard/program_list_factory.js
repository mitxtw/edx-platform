;(function (define) {
    'use strict';

    define([
        'js/learner_dashboard/views/collection_list_view',
        'js/learner_dashboard/views/sidebar_view',
        'js/learner_dashboard/views/program_card_view',
        'js/learner_dashboard/collections/program_collection',
        'js/learner_dashboard/collections/program_progress_collection'
    ],
    function (CollectionListView, SidebarView, ProgramCardView, ProgramCollection, ProgressCollection) {
        return function (options) {
            var progressCollection = new ProgressCollection();

            progressCollection.set(options.userProgress || []);
            options.progressCollection = progressCollection; 

            new CollectionListView({
                el: '.program-cards-container',
                childView: ProgramCardView,
                collection: new ProgramCollection(options.programsData),
                context: options
            }).render();

            new SidebarView({
                el: '.sidebar',
                context: options
            }).render();
        };
    });
}).call(this, define || RequireJS.define);
