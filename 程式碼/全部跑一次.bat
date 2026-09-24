@echo off
set PYTHONIOENCODING=utf-8
set PY=python
if not exist 紀錄 mkdir 紀錄
echo 開始 %date% %time% > 紀錄\00_總覽.txt

echo [1/10] 接續規則檢查
%PY% check_rules.py 反向抽鬼牌vC7_0922v6.py 反向抽鬼牌vC7a_0922v6.py 反向抽鬼牌vC7b_0922v6.py 反向抽鬼牌vC7_0919前_0922v6.py 反向抽鬼牌vC7a_中間版_0922v6.py > 紀錄\01_接續規則.txt 2>&1

echo [2/10] 十萬局輪數分布，六次，約 15 分鐘
%PY% stats_v3.py 反向抽鬼牌vC7_0922v6.py on 100000 > 紀錄\02a_最終版_有坍縮.txt 2>&1
%PY% stats_v3.py 反向抽鬼牌vC7_0922v6.py off 100000 > 紀錄\02b_最終版_無坍縮.txt 2>&1
%PY% stats_v3.py 反向抽鬼牌vC7a_0922v6.py on 100000 > 紀錄\02c_抽牌順序_有坍縮.txt 2>&1
%PY% stats_v3.py 反向抽鬼牌vC7a_0922v6.py off 100000 > 紀錄\02d_抽牌順序_無坍縮.txt 2>&1
%PY% stats_v3.py 反向抽鬼牌vC7b_0922v6.py on 100000 > 紀錄\02e_丟對子時機_有坍縮.txt 2>&1
%PY% stats_v3.py 反向抽鬼牌vC7b_0922v6.py off 100000 > 紀錄\02f_丟對子時機_無坍縮.txt 2>&1

echo [3/10] vC6.1，兩次，約 6 分鐘
%PY% stats_basic.py 反向抽鬼牌vC6_1_0922v6.py on 100000 > 紀錄\03a_vC61_有坍縮.txt 2>&1
%PY% stats_basic.py 反向抽鬼牌vC6_1_0922v6.py off 100000 > 紀錄\03b_vC61_無坍縮.txt 2>&1

echo [4/10] 中間版本的逐輪不變量，兩次，約 8 分鐘
%PY% invariant_per_turn.py -e 反向抽鬼牌vC7a_中間版_0922v6.py -n 100000 --no-cap > 紀錄\04a_中間版_有坍縮.txt 2>&1
%PY% invariant_per_turn.py -e 反向抽鬼牌vC7a_中間版_0922v6.py -n 100000 --no-cap --no-collapse > 紀錄\04b_中間版_無坍縮.txt 2>&1

echo [5/10] 構造測試
%PY% ct_table.py 反向抽鬼牌vC6_1_0922v6.py 反向抽鬼牌vC7a_0922v6.py 反向抽鬼牌vC7b_0922v6.py 反向抽鬼牌vC7_0922v6.py > 紀錄\05_構造測試.txt 2>&1

echo [6/10] 消融 M1 到 M8，約 10 分鐘
for %%M in (M1 M2 M3 M4 M5 M6 M7 M8) do %PY% ablation_v6.py -e 反向抽鬼牌vC7_0922v6.py --only %%M > 紀錄\06_消融_%%M.txt 2>&1

echo [7/10] 規則落實修正前的量測
%PY% m20k.py 反向抽鬼牌vC7_0919前_0922v6.py 20000 > 紀錄\07_修正前量測.txt 2>&1

echo [8/10] 事件重播
%PY% run_demo.py --seed 42 -e 反向抽鬼牌vC7_0922v6.py > 紀錄\08a_對局紀錄.txt 2>&1
%PY% replay_verify.py > 紀錄\08b_重播比對.txt 2>&1

echo [9/10] 五局版與規則發生頻率
%PY% 反向抽鬼牌vD3_0922v6.py > 紀錄\09a_五局版_seed42.txt 2>&1
%PY% m_vd3.py 反向抽鬼牌vD3_0922v6.py 10000 > 紀錄\09b_五局版_一萬次.txt 2>&1
%PY% freq.py 反向抽鬼牌vC7_0922v6.py 20000 > 紀錄\09c_規則發生頻率.txt 2>&1

echo [10/10] 三人殘局展開
%PY% endgame_3p.py > 紀錄\10_三人殘局.txt 2>&1

echo 結束 %date% %time% >> 紀錄\00_總覽.txt
echo.
echo 全部跑完，結果在 紀錄 資料夾裡
pause
