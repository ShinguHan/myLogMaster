def load_data_from_cache(self):
        """로컬 캐시에서 데이터를 로드하고, 데이터 유무와 상관없이 항상 UI에 모델을 업데이트하도록 신호를 보냅니다."""
        if not self.db_manager: 
            self.update_model_data(pd.DataFrame()) # DB 매니저가 없을 때도 초기 모델 전송
            return
        
        print("Loading initial data from local cache...")
        cached_data = self.db_manager.read_all_logs_from_cache()
        
        if not cached_data.empty:
            self.original_data = cached_data
            if 'SystemDate' in self.original_data.columns and 'SystemDate_dt' not in self.original_data.columns:
                 self.original_data['SystemDate_dt'] = pd.to_datetime(self.original_data['SystemDate'], format='%d-%b-%Y %H:%M:%S:%f', errors='coerce')
            print(f"Loaded {len(cached_data)} rows from cache.")
        else:
            self.original_data = pd.DataFrame() # 캐시가 비었으면 빈 데이터프레임으로 초기화
            print("Local cache is empty.")
        
        # ✅ 데이터가 있든 없든, 무조건 UI에 모델을 설정하라는 신호를 보냅니다.
        self.update_model_data(self.original_data)