# -*- coding: utf-8 -*-
"""
app.py - Flaskベース学習支援ウェブアプリ
"""
from flask import Flask, render_template, request, jsonify, session
import chat_state as lca  # 既存のコンソール版アプリを再利用
import json
import os
import uuid
from flask_session import Session
from flask import redirect, url_for

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config["SESSION_TYPE"] = "filesystem"  # ← cookieじゃなくファイルに保存
app.config["SESSION_FILE_DIR"] = "./.flask_session/"
app.config["SESSION_PERMANENT"] = False
Session(app)

MISTAKE_FILE = "mistakes.json"
def save_mistakes_from_session():
    """session["evaluations"] から不正解の問題を mistakes.json に保存"""
    try:
        ev_list = session.get("evaluations", [])
        mistakes = []

        # 既存ファイルの中身を読む
        if os.path.exists(MISTAKE_FILE):
            with open(MISTAKE_FILE, "r", encoding="utf-8") as f:
                mistakes = json.load(f)

        # 不正解だけ追加
        for ev in ev_list:
            if ev.get("result") == "不正解":
                data = {
                    "id": str(uuid.uuid4()),  # ユニークなIDを生成
                    "question_number": ev.get("question_number"),
                    "question_text": ev.get("question_text"),
                    "options": ev.get("options"),
                    "correct_answer": ev.get("correct_answer"),
                    "explanation": ev.get("explanation")
                }
                mistakes.append(data)

        # 上書き保存
        with open(MISTAKE_FILE, "w", encoding="utf-8") as f:
            json.dump(mistakes, f, ensure_ascii=False, indent=2)

        print("mistakes.json に保存しました:", len(mistakes), "件")
    except Exception as e:
        print("保存失敗:", e)
@app.route("/review")
def review():
    mistakes = []
    if os.path.exists(MISTAKE_FILE):
        with open(MISTAKE_FILE, "r", encoding="utf-8") as f:
            mistakes = json.load(f)
    print("Loaded mistakes:", len(mistakes), "items")
    return render_template("review.html", mistakes=mistakes)
def save_mistake(ev):
    try:
        if ev.get("result") == "不正解":
            data = {
                "question_text": ev.get("question_text"),
                "options": ev.get("options"),
                "correct_answer": ev.get("correct_answer"),
                "explanation": ev.get("explanation")
            }

            # 既存ファイル読み込み
            if os.path.exists(MISTAKE_FILE):
                with open(MISTAKE_FILE, "r", encoding="utf-8") as f:
                    mistakes = json.load(f)
            else:
                mistakes = []

            mistakes.append(data)

            # 上書き保存
            with open(MISTAKE_FILE, "w", encoding="utf-8") as f:
                json.dump(mistakes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("保存失敗:", e)



@app.route('/', methods=['GET'])
def index():
    return render_template(
        'index.html',
        genre_options=lca.GENRE_OPTIONS,
        level_options=lca.LEVEL_OPTIONS
    )

@app.route('/start', methods=['POST'])
def start():
    # ★ 過去の記録をリセット
    session.pop("evaluations", None)
    session.pop("analysis", None)
    session.pop("last_question", None)

    genre_key = request.form['genre']
    level_key = request.form['level']
    if genre_key=="復習":
        return redirect(url_for('review'))

    if genre_key in lca.GENRE_OPTIONS:
        genre = lca.GENRE_OPTIONS[genre_key]
    else:
        genre = genre_key

    if level_key in lca.LEVEL_OPTIONS:
        level = lca.LEVEL_OPTIONS[level_key]
    else:
        level = "普通"
    
    system_prompt = lca.PROMPT_TEMPLATE.format(
        GENRE=genre,
        LEVEL=level,
        MAX_COUNT=lca.MAX_COUNT
    )
    lca.messages.clear()
    lca.messages.append({"role": "system", "content": system_prompt})

    first_question = lca.chat_once("一問目を出題してください")
    print(f"First Question: {first_question}")

    # ★ 一問目は evaluations には保存しない → last_question にだけ保持
    try:
        parsed = json.loads(first_question)
        if isinstance(parsed, dict) and parsed.get("type") == "question":
            session["last_question"] = parsed
        session["evaluations"] = []
    except Exception:
        session["evaluations"] = []

    return render_template('chat.html', first_question=first_question)
@app.route("/delete_mistake", methods=["POST"])
def delete_mistake():
    """mistakes.json から特定の問題を削除"""
    data = request.get_json()
    target_id = data.get("id")

    if not os.path.exists(MISTAKE_FILE):
        return jsonify({"status": "error", "message": "ファイルが存在しません"})

    with open(MISTAKE_FILE, "r", encoding="utf-8") as f:
        mistakes = json.load(f)

    # uuid が一致する最初の1件を削除
    mistakes = [m for m in mistakes if m.get("id") != target_id]

    with open(MISTAKE_FILE, "w", encoding="utf-8") as f:
        json.dump(mistakes, f, ensure_ascii=False, indent=2)

    return jsonify({"status": "ok", "message": f"問題  を削除しました"})

@app.route('/api/message', methods=['POST'])
def api_message():
    data = request.get_json()
    user_msg = data.get('message', '').strip()
    chosen_text = data.get('chosen_text')

    # --- end 押下時 ---
    if user_msg == "end":
        # ★ 未回答の last_question が残っていれば「未回答」として evaluations に追加
        last_q = session.get("last_question")
        if last_q:
            ev_list = session.get("evaluations", [])
            already_saved = any(ev.get("question_number") == last_q.get("question_number") for ev in ev_list)
            if not already_saved:
                ev_list.append({
                    "question_number": last_q.get("question_number"),
                    "question_text": last_q.get("question_text"),
                    "options": last_q.get("options"),
                    "chosen_answer": None,
                    "result": "未回答",
                    "explanation": "この問題には解答しませんでした。",
                    "type": "evaluation"
                })
                session["evaluations"] = ev_list
            session.pop("last_question", None)

        analysis = session.get("analysis")
        if not analysis:
            # GPT に途中終了用の analysis をリクエスト
            prompt = "学習を途中終了します。ここまでの結果をもとに必ず analysis JSON を出力してください。"
            bot_reply = lca.chat_once(prompt)
            try:
                analysis = json.loads(bot_reply)
            except Exception:
                analysis = {
                    "type": "analysis",
                    "statistics": {
                        "accuracy_rate": "0%",
                        "total_questions": len(session.get("evaluations", [])),
                        "correct_answers": 0
                    },
                    "overall_evaluation": "手動終了しました。",
                    "strengths": [],
                    "improvements": [],
                    "advice": "また挑戦してみてください。"
                }
        session["analysis"] = analysis
        return jsonify({"reply": json.dumps(analysis, ensure_ascii=False), "redirect": "/result"})

    # --- 通常フロー ---
    bot_reply = lca.chat_once(user_msg)

    parsed = None
    try:
        parsed = json.loads(bot_reply)
    except:
        pass

    # --- question ---
    if isinstance(parsed, dict) and parsed.get("type") == "question":
        session["last_question"] = parsed

    # --- evaluation ---
    if isinstance(parsed, dict) and parsed.get("type") == "evaluation":
        ev_list = session.get("evaluations", [])
        last_q = session.get("last_question")
        parsed["correct_answer"] = last_q.get("correct_answer") if last_q else None  # ★ 正解番号を保存
        parsed["question_number"] = last_q.get("question_number") if last_q else None
        parsed["question_text"] = last_q.get("question_text") if last_q else ""
        parsed["options"] = last_q.get("options") if last_q else []

        parsed["chosen_answer"] = {
            "number": user_msg,
            "text": chosen_text or ""
        }
        if parsed["result"] == "不正解":
            save_mistake({
                "question_number": parsed["question_number"],
                "question_text": parsed["question_text"],
                "options": parsed["options"],
                "correct_answer": parsed.get("correct_answer"),
                "explanation": parsed["explanation"]
            })
        # ★ 同じ question_number のデータを削除して上書き
        ev_list = [ev for ev in ev_list if ev.get("question_number") != parsed["question_number"]]
        ev_list.append(parsed)
        session["evaluations"] = ev_list
        
        # 回答済みになったので last_question をクリア
        session.pop("last_question", None)

        if session.get("analysis"):
            return jsonify({"reply": bot_reply, "redirect": "/result"})

    # --- evaluation + analysis ---
    if isinstance(parsed, list):
        eval_data = None
        analysis_data = None
        for item in parsed:
            if item["type"] == "evaluation":
                eval_data = item
            elif item["type"] == "analysis":
                analysis_data = item

        if eval_data:
            last_q = session.get("last_question")
            eval_data["question_number"] = last_q.get("question_number") if last_q else None
            eval_data["question_text"] = last_q.get("question_text") if last_q else ""
            eval_data["options"] = last_q.get("options") if last_q else []
            eval_data["chosen_answer"] = {
                "number": user_msg,
                "text": chosen_text or ""
            }

            ev_list = session.get("evaluations", [])
            ev_list = [ev for ev in ev_list if ev.get("question_number") != eval_data["question_number"]]
            ev_list.append(eval_data)
            session["evaluations"] = ev_list

        if analysis_data:
            session["analysis"] = analysis_data

        # 最終問題なので必ずリダイレクト
        return jsonify({"reply": bot_reply, "redirect": "/result"})

    return jsonify({"reply": bot_reply})


@app.route("/result")
def result():
    evaluations = session.get("evaluations", [])
    analysis = session.get("analysis")
    save_mistakes_from_session()
    return render_template("result.html", evaluations=evaluations, analysis=analysis)

if __name__ == '__main__':
    app.run(debug=True)


