(function (define) {
  'use strict';
  define([
          'backbone',
          'js/learner_dashboard/models/program_progress_model'
    ],
    function (Backbone, ProgressModel) {
      return Backbone.Collection.extend({
          model: ProgressModel
      });
  });
}).call(this, define || RequireJS.define);
