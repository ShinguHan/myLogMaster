def _create_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        open_action = QAction("&Open Log File...", self)
        open_action.triggered.connect(self.open_log_file)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 'View' menu now contains the 'Theme' submenu
        self.view_menu = menu_bar.addMenu("&View")
        
        theme_menu = self.view_menu.addMenu("Theme")
        theme_group = QActionGroup(self)

        themes = ["light", "dark"] 
        for theme in themes:
            action = QAction(theme.capitalize(), self, checkable=True)
            action.triggered.connect(lambda checked, t=theme: self._apply_theme(t))
            theme_group.addAction(action)
            theme_menu.addAction(action)
            
            if self.controller.get_current_theme() == theme:
                action.setChecked(True)

        self.view_menu.addSeparator()

        select_columns_action = QAction("&Select Columns...", self)
        select_columns_action.triggered.connect(self.open_column_selection_dialog)
        self.view_menu.addAction(select_columns_action)
        
        self.view_menu.addSeparator()
        
        dashboard_action = QAction("Show Dashboard...", self)
        dashboard_action.triggered.connect(self.show_dashboard)
        self.view_menu.addAction(dashboard_action)

        # 'Tools' menu remains the same
        self.tools_menu = menu_bar.addMenu("&Tools")
        query_builder_action = QAction("Advanced Filter...", self)
        query_builder_action.triggered.connect(self.open_query_builder)
        self.tools_menu.addAction(query_builder_action)
        clear_filter_action = QAction("Clear Advanced Filter", self)
        clear_filter_action.triggered.connect(self.clear_advanced_filter)
        self.tools_menu.addAction(clear_filter_action)
        self.tools_menu.addSeparator()
        
        self.scenario_menu = self.tools_menu.addMenu("Run Scenario Validation")
        self.tools_menu.aboutToShow.connect(self.populate_scenario_menu)

        browse_scenarios_action = QAction("Browse Scenarios...", self)
        browse_scenarios_action.triggered.connect(self.open_scenario_browser)
        self.tools_menu.addAction(browse_scenarios_action)
        self.tools_menu.addSeparator()
        script_editor_action = QAction("Analysis Script Editor...", self)
        script_editor_action.triggered.connect(self.open_script_editor)
        self.tools_menu.addAction(script_editor_action)

        # 'Help' menu remains the same
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About...", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)