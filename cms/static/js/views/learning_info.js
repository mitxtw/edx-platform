// Backbone Application View: Course Learning Information

define([ // jshint ignore:line
    'jquery',
    'underscore',
    'backbone',
    'gettext',
    'js/utils/templates'
],
function ($, _, Backbone, gettext, TemplateUtils) {
    'use strict';
    var LearningInfoView = Backbone.View.extend({
        tagName: 'div',

        initialize: function(options) {
            // Set up the initial state of the attributes set for this model instance
             _.bindAll(this, 'render');
            this.template = this.loadTemplate('course-settings-learning-fields');
            this.index = options.index;
            this.info = options.info;
        },

        loadTemplate: function(name) {
            // Retrieve the corresponding template for this model
            return TemplateUtils.loadTemplate(name);
        },

        render: function() {
            // Assemble the editor view for this model
            return $(this.el).append(this.template({info: this.info, index: this.index}));
        }

    });
    return LearningInfoView;
});
