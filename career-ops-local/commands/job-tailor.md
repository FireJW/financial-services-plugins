rld",
          allFrames: true,
          js: ["public/js/inject.js"],
          runAt: "document_start",
          world: "MAIN",
          matches: ["<all_urls>"],
          excludeMatches: ["*://localhost/*", "*://*.localhost/"]
        }
      ]);
    }
  };

  // shared/js/background/components/email-autofill.js
  var import_webextension_polyfill11 = __toESM(require_browser_polyfill());
  init_pixels();
  init_message_handlers();
  var import_tldts6 = __toESM(require_cjs());
  init_tds();
  init_utils();
  init_wrapper();
  var MENU_ITEM_ID = "ddg-autofill-context-menu-item";
  var REFETCH_ALIAS_ALARM = "refetchAlias";
  var REFETCH_ALIAS_ATTEMPT = "refetchAliasAttempt";
  var EmailAutofill = class {
    /**
     * @param {{
     *  settings: import('../settings.js');
     * }} options
     */
    constructor({ settings: settings22 }) {
      this.settings = settings22;
      this.contextMen