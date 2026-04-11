"""pc_cockpit/views/helpers — view helper 패키지 (R6 cleanup).

workflow.py / parameter_editor.py god view 를 슬림화하기 위해 P207/P208/P209
의 Streamlit 렌더링 블록을 이 패키지로 추출한다.

구조:
- `allocation_panel.py` — P207 allocation 관련 렌더러
- `holding_structure_panel.py` — P208 holding structure 관련 렌더러
- `drawdown_contribution_panel.py` — P209 drawdown contribution 관련 렌더러

각 helper 는 순수 view 함수 (Streamlit 호출 + 입력 data) 로 분리되며
비즈니스 로직을 포함하지 않는다. 데이터는 이미 build 된 bt_meta /
base_dir / params 등을 받는다.
"""
