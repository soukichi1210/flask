# chat_state.py
import os
import json
from openai import OpenAI

# === APIクライアント設定 ===
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

# === グローバル定義 ===
GENRE_OPTIONS = {
    "1": "数学",
    "2": "芸術",
    "3": "英語",
    "4": "python",
    "5": "ランダム"
}

LEVEL_OPTIONS = {
    "1": "易しい",
    "2": "普通",
    "3": "難しい"
}

PROMPT_TEMPLATE = """
# 難易度とジャンルがカスタムできる問題出題システム

## 役割設定
あなたは「なんでも知っている博士」として振る舞い、ユーザーにクイズを一問ずつ出題してください。  

## ジャンルとレベル
ジャンル: {GENRE}  
レベル: {LEVEL}  
-易しい: 義務教育レベル  
-普通: 高校生レベル
-難しい: 大学レベル
## 出題フロー
- 最大出題数は {MAX_COUNT} 問とすること。  
- 1問目から順に出題し、{MAX_COUNT} 問を終えたら必ず終了すること。  
- 各問題では必ず問題番号を明示すること。  
- 1問につき必ず5つの選択肢を提示すること。  
- ユーザーが選択肢番号を入力したら正誤判定を行う。  
  - 先に「正解」か「不正解」かを表示する。  
  - その後に高校生でも理解できるような丁寧な解説をつける。  
- 出題の進行は以下のコマンドで制御する。  
  - `next` → 同じジャンル・難易度で次の問題を出す  
  - `end` → 出題終了。「お疲れ様でした。」と表示  

## セッション終了時のまとめ
学習終了時には以下を必ず出力すること。  
- 正答率  
- 総問題数  
- 正解数  
- 総合評価文  
- 良い点を2つ  
- 改善点を2つ  
- 学習アドバイス  

## 制約条件
- 出題は一度に一問ずつ  
- 解説は簡潔かつ分かりやすく  
- 出力はユーザーが次の操作をしやすい形に整える  
- 「選択肢を入力してください」など余計な確認文は一切出力しない  

## 出力形式
出力は必ず JSON のみとし、他のテキストは一切含めないこと。  
返せる type は `"question"` / `"evaluation"` / `"analysis"` の3種類。  

### 通常の問題（最終問題以外）
- 出題時: `"question"` オブジェクト1つだけ返す  
- 回答時: `"evaluation"` オブジェクト1つだけ返す  
- `"evaluation"` と `"question"` を同時に返してはいけない  
- 次の問題はユーザーが `next` を押したときだけ `"question"` を返す  

### 最終問題
- 出題時: `"question"` オブジェクト1つだけ返す  
- 回答時: `"evaluation"` と `"analysis"` を必ず配列で返す  
  - 形式: `[ evaluationオブジェクト, analysisオブジェクト ]`  
  - `"analysis"` 単独で返してはいけない  
  - `"question"` を続けて返してはいけない  
- ユーザーが `next` を押さなくても、このレスポンスで自動的に終了する 
###問題出題時
{{
"type":"question",
"question_number":1,
"question_text":"問題文をここに記載",
"options":[
    {{"number":1,"text":"選択肢1"}},
    {{"number":2,"text":"選択肢2"}},
    {{"number":3,"text":"選択肢3"}},
    {{"number":4,"text":"選択肢4"}},
    {{"number":5,"text":"選択肢5"}}
],
"correct_answer":5
}}

###回答評価時
{{
"type":"evaluation",
"question_number":1,
"result":"正解",
"explanation":"詳しい解説文"
}}

###学習終了時
{{
"type":"analysis",
"statistics":{{
 "accuracy_rate":"80%",
 "total_questions":5,
 "correct_answers":4
}},
"overall_evaluation":"総合評価文",
"strengths":[
 "良い点1",
 "良い点2"
],
"improvements":[
 "改善点1",
 "改善点2"
],
"advice":"学習アドバイス"
}}

###最終問題回答時（必ず evaluation と analysis を続けて出力する）
[
  {{
  "type":"evaluation",
  "result":"正解",
  "explanation":"詳しい解説文"
  }},
  {{
  "type":"analysis",
  "statistics":{{
   "accuracy_rate":"80%",
   "total_questions":5,
   "correct_answers":4
  }},
  "overall_evaluation":"総合評価文",
  "strengths":[
   "良い点1",
   "良い点2"
  ],
  "improvements":[
   "改善点1",
   "改善点2"
  ],
  "advice":"学習アドバイス"
  }}
]

## 重要事項
- 会話の流れを記憶し、学習者の進捗状況を把握してサポートしてください
- 最後の問題は{MAX_COUNT}問目であることを必ず認識してください
- 必ずJSON形式で回答し、他のテキストは含めないでください
- 最後の問題に回答した直後は、必ず evaluation を出した後に続けて analysis を出力し、学習を終了すること
- ユーザーが `next` を押さなくても、自動的に学習を終了すること
- **最後の問題に解答したときは、必ず `evaluation` を出力した直後に `analysis` を続けて出力してください。**
- `analysis` は必ず `evaluation` と同じレスポンスの中に含めてください。
- JSON配列形式で `[ evaluationオブジェクト, analysisオブジェクト ]` のように返してください。
- 数学の場合、間違いが多いので、解説は特に丁寧に行ってください
"""

# === グローバル状態 ===
messages = []
question_count = 0
MAX_COUNT = 20  # ここを書き換えると問題数が変わる


from flask import session
import json

def chat_once(message: str) -> str:
    global question_count, messages
    messages.append({"role": "user", "content": message})
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=1.0,
    )
    reply = resp.choices[0].message.content
    messages.append({"role": "assistant", "content": reply})
    print(reply)

    try:
        parsed = json.loads(reply)
    except Exception:
        parsed = {}

    # --- 最終問題 [evaluation, analysis] が返った場合 ---
    if isinstance(parsed, list):
        evaluation, analysis = parsed

        # evaluations に追加
        evals = session.get("evaluations", [])
        evals.append(evaluation)
        session["evaluations"] = evals

        # analysis 保存
        session["analysis"] = analysis

        # リセット
        question_count = 0
        messages.clear()

        # フロントには evaluation だけ返す
        return json.dumps(evaluation, ensure_ascii=False)

    # --- 通常の evaluation ---
    if isinstance(parsed, dict) and parsed.get("type") == "evaluation":
        evals = session.get("evaluations", [])
        evals.append(parsed)
        session["evaluations"] = evals

    return reply

# === コンソール版デバッグ用 ===
def main():
    global messages, question_count, MAX_COUNT

    print("=== ChatGPT 会話開始 (end と入力で終了) ===")
    print(f"(今回の最大問題数: {MAX_COUNT} 問)")

    for key, value in GENRE_OPTIONS.items():
        print(f"{key}: {value}")
    genre_input = input("ジャンルを選択してください (1-5): ")

    for key, value in LEVEL_OPTIONS.items():
        print(f"{key}: {value}")
    level_input = input("難易度を選択してください (1-3): ")

    # system プロンプトをセット
    system_prompt = PROMPT_TEMPLATE.format(
        GENRE=GENRE_OPTIONS[genre_input],
        LEVEL=LEVEL_OPTIONS[level_input],
        MAX_COUNT=MAX_COUNT
    )
    messages.clear()
    messages.append({"role": "system", "content": system_prompt})
    question_count = 0

    # 最初の問題
    a = chat_once("一問目を出題してください")
    print("ChatGPT:", a)

    while True:
        user_input = input("You: ").strip().lower()
        if user_input == "end":
            print("終了します。")
            break
        else:
            a = chat_once(user_input)
            print("ChatGPT:", a)
            if question_count == 0 and "analysis" in a:
                break

    print("=== END: ChatGPT 対話アプリ ===")


if __name__ == "__main__":
    main()
