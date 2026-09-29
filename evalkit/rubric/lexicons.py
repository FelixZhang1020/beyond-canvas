"""Bilingual phrase lists for the feedback rubric.

The Chinese strings here are domain data, not code written in Chinese: they are
the phrases a grader must recognise in Chinese feedback. They belong in this
file and nowhere else in the codebase.

Every list is deliberately strict. A grader that lets a borderline phrase pass
teaches nothing; a grader that flags one costs the author ten seconds.
"""

from __future__ import annotations

import re

PERSON_PRAISE = {
    "en": (
        re.compile(
            r"\byou(?:'re| are)\s+(?:so\s+|such\s+|really\s+|very\s+)?(?:a\s+|an\s+)?"
            r"(?:talented|gifted|good|great|amazing|creative|artistic|clever|smart)\b"
        ),
        re.compile(r"\byou have (?:a |such a )?(?:gift|talent)\b"),
        re.compile(r"\b(?:natural|born|real) artist\b"),
        re.compile(r"\byou(?:'re| are) (?:an? )?artist\b"),
    ),
    "zh": (
        re.compile(r"你(?:真|好|很|太)?(?:有天赋|有天分|棒|厉害|聪明|能干)"),
        re.compile(r"你(?:真)?是(?:个)?小?(?:画家|艺术家|天才)"),
    ),
}

COMPARISON = {
    "en": ("better than", "the best", "best in", "than other", "than the other",
           "compared to", "more beautiful than", "nicer than"),
    "zh": ("比其他", "比别的", "比其它", "最好", "最棒", "最漂亮", "第一名", "比大家"),
}

CORRECTION = {
    # Widened because a plain correction — "you should make the roof
    # straighter", "try making the line longer" — passed every phrase here, on
    # the entrance where rule 6 is absolute. The sketch entrance skips this rule
    # entirely, so "you could try" belongs on the list: it is the approved form
    # THERE and a correction HERE.
    "en": ("should have", "should be", "you should", "you could try", "you can try",
           "try making", "try adding", "try to make", "make it more", "would look better",
           "would be better", "needs more", "you forgot", "is missing", "are missing",
           "instead of", "next time try", "needs to be", "not quite right", "mistake",
           "not in the picture", "isn't in the picture", "not in the drawing", "isn't in the drawing",
           "the picture only has", "the drawing only has"),
    "zh": ("应该", "本来该", "你忘了", "少画了", "漏了", "而不是", "下次可以", "不对", "错了",
           "可以试试", "试着画", "改一改", "会更好", "再加一点",
           # Widened: a reply told a child whose story had a tree "but I only see the
           # brothers and the dog in the picture, where is the tree?". Only phrases about the
           # picture itself: a character in the story may say it cannot see something.
           "画里只有", "画里没有", "画里看不到", "画里没看到", "画上只有", "画上没有",
           "画面上没有", "画面里没有", "图里只有", "图里没有",
           # Live on the class page soon after: "but you only drew the ball at his feet, where
           # are the boy's hands?" to a child who had said they were stuck.
           "你只画了", "只画了一", "你没有画", "你没画", "没有画出", "没画出"),
}

# Feelings a reply may not give a character on its own (rule 14), checked without a model. Added
# because the class's judge, Qwen with its thinking off, passed "it must be so happy fetching the
# ball back" five times in five on a child who had said only that the dog wagged its tail. A feeling
# the child named, or one the reply only asks about, is not listed (loop.py).
FEELINGS = {
    "en": ("happy", "glad", "sad", "scared", "afraid", "frightened", "angry", "upset", "excited",
           "lonely", "worried", "nervous", "proud", "tired", "jealous", "disappointed"),
    "zh": ("开心", "高兴", "快乐", "兴奋", "激动", "幸福", "得意", "满足", "难过", "伤心", "害怕",
           "生气", "着急", "担心", "紧张", "孤单", "孤独", "寂寞", "失望", "委屈", "害羞", "骄傲",
           "很累", "好累", "又累", "累了", "累坏", "乐坏"),
}

# "You" said to more than one: a reply to one child that says it is talking to the story's characters,
# unless the child spoke of them as "we" (rule 14). Found in a reply: "where will you go first?" of
# two brothers the child called "they", passed by the judge. Chinese only: English "you" is both.
YOU_PLURAL_ZH = "你们"
WE_ZH = ("我们", "咱们", "你们")

# A question that asks WHY about a feeling takes the feeling as given (rule 14): "why is he so happy?"
# gives him happiness the child never mentioned (code review). Asking HOW he feels does not.
PRESUPPOSING = {
    "en": ("why",),
    "zh": ("为什么", "为何", "怎么这么", "怎么那么", "怎么会这么"),
}

REALISM = {
    "en": ("realistic", "looks real", "look real", "like a real", "lifelike",
           "doesn't look like", "does not look like", "out of proportion", "anatomically"),
    "zh": ("像真的", "不像", "逼真", "写实", "比例不对", "不太像", "画得不准"),
}

DIMINISHING = {
    "en": ("just a", "just some", "only a", "simple", "rough", "messy",
           "childish", "scribble", "crude", "basic little"),
    "zh": ("简单", "只是", "有点乱", "潦草", "幼稚", "涂鸦", "粗糙", "随便画"),
}

# The lists below serve the structural rules rather than the phrase rules, but
# they live here for the same reason as the rest: this is the one file allowed
# to hold Chinese. They moved out of structural.py.

OBSERVATION_OPENERS = {
    "en": ("i see", "i notice", "i can see", "i spot", "looking at", "here i see"),
    "zh": ("我看到", "我注意到", "我发现", "我看见", "我瞧见"),
}

EVALUATIVE_WORDS = {
    "en": ("beautiful", "lovely", "nice", "pretty", "wonderful", "amazing", "great",
           "perfect", "excellent", "cute", "gorgeous", "fantastic", "brilliant"),
    "zh": ("漂亮", "好看", "美丽", "真棒", "太棒", "完美", "可爱", "优秀", "厉害", "了不起"),
}

# Widened on the Chinese side on the first run this rubric ever had
# in Chinese. Four of six sketch questions were failed as closed, and every one
# of them was open: "which part was hardest to judge", "which part did you adjust
# most", "what was the process like". The list carried "which place" but not
# "which one", and one of the two words for "how" but not the other two — the
# English half had been widened twice for exactly this reason, and the Chinese
# half had never been measured at all.
OPEN_MARKERS = {
    "en": ("what", "how", "why", "who", "where", "which", "tell me"),
    "zh": ("什么", "怎么", "怎样", "如何", "为什么", "谁", "哪里", "哪儿",
           "哪个", "哪一", "哪部分", "哪些", "什么样", "说说", "讲讲", "多久", "多少"),
}

# English marks a closed question with its opening verb; Chinese marks it with a
# final particle. The two need different shapes, so they are two constants
# rather than one bilingual dict.
YES_NO_OPENERS_EN = ("is ", "are ", "do ", "does ", "did ", "can ", "could ", "will ",
                     "would ", "have ", "has ", "was ", "were ", "should ", "am ")
CLOSED_QUESTION_MARKERS_ZH = ("吗？", "吗?")
# Invitations to tell: "能说说...吗" is answered with a story, not yes or no, though it ends in 吗 (rule 9).
INVITATIONS_ZH = ("说说", "讲讲", "告诉我")
# A Chinese clause that ends in one of these asks, even when a comma follows instead of a question
# mark: "它心里开心吗，还是想再玩？" is two questions (evalkit/rubric/quotes.py).
QUESTION_PARTICLES_ZH = ("吗", "呢")

QUESTION_MARKS = ("?", "？")

# --- Rules 12 to 14: the loop, not the comment -------------------------------

# Questions about the artifact rather than the world inside it. The spec names
# this failure exactly: asking what was drawn returns a list of nouns, while
# asking what is happening returns a story.
ARTIFACT_QUESTIONS = {
    "en": ("what did you draw", "what is this", "what are these", "what did you make",
           "what is that", "what colour is", "what color is", "how did you draw"),
    "zh": ("你画了什么", "这是什么", "这些是什么", "画的是什么", "你画的什么"),
}

# Markers that a question reaches inside the picture: events, characters, the
# unseen, the senses, inner state, or before and after.
#
# THIS LIST WAS WIDENED THREE TIMES IN ONE DAY, from three sweeps of the same
# fourteen drawings, and every widening was prompted by a question that deserved
# to pass. That is the honest signal about the approach rather than about the
# words: a keyword list cannot decide whether a question enters a world, so its
# false-negative rate is real and unbounded, and each sweep will keep finding new
# vocabulary. The two ways out are a judge call when no marker matches, which
# costs a model call per grade, or accepting the rate and measuring it. Neither
# is chosen here, because it is a change to a settled rule rather than a defect.
# See docs/measured/entrance-live-run.md.
#
# Widened after a live run marked down two questions that are exactly
# what this rule wants. "What would happen if I stepped through that space?" was
# failed because the list carried "happening" and "happened" but not the stem;
# the stem now covers all three. "What is hiding under the fuzzy skin?" was
# failed because the unseen, which section 5a names as the class that forces
# invention hardest, had no words on the list at all.
# How the machine announces that it is speaking AS something in the picture.
# Section 3.5 calls this the strongest rung — 最强的一种 — and its own worked
# example, 我是那只鸟，我能停在你的树上吗？, failed rule 12 on every marker list
# anyone could write, because a character introducing itself contains none of the
# words a question about events contains. The form is the signal, not the words.
CHARACTER_VOICE = {
    "en": ("i am ", "i'm ", "i am the", "it's me,"),
    "zh": ("我是", "我就是"),
}

WORLD_MARKERS = {
    "en": ("happen", "going to", "next", "before", "after", "where is",
           "where are", "who", "why", "how did", "feel", "think", "want", "hear",
           # "under" is deliberately absent: it sits at the front of "understand",
           # and "do you understand?" is not a question about the world.
           "smell", "sound", "outside", "inside", "behind", "hiding",
           # "looking" and "watching", not "look": a character's gaze is inner
           # state, while "what does it look like?" is a question about the
           # artifact. The front-anchored match keeps the two apart.
           "hidden", "live", "doing", "name", "play", "world", "looking", "watching",
           # Movement, added when rungs began to be graded by this
           # rule. The second rung is a choice between two things a character
           # might be doing — "standing still, or walking away?" — and none of
           # those words was here, so the ladder's own device failed the rule
           # that is supposed to reward it.
           "walking", "running", "flying", "going", "coming", "arriving",
           "leaving", "standing", "sitting", "sleeping", "waiting",
           "adventure", "story"),
    # Widened from eight real children's paintings, where this rule
    # failed five of them and every failure was a good question. The misses were
    # ordinary Chinese: 做什么 is the most natural way to ask what is happening,
    # 听到 is the everyday form of 听见, and 如果我站在 is the sensory question
    # section 3.4 recommends by name — the rule was failing the very form the
    # requirements ask for.
    "zh": ("发生", "接下来", "刚刚", "以前", "后来", "去哪", "在想", "觉得", "感觉",
           "听见", "听到", "看到", "闻到", "尝到", "摸到", "站在", "做什么", "正在",
           "打算", "发现", "外面", "里面", "下面", "后面", "藏", "住在", "叫什么",
           "为什么", "怎么来",
           # Widened again, from twelve real paintings in Chinese.
           # "Where is this river flowing to?" was failed for not reaching inside
           # the picture. The English half has carried "where is", "where are",
           # "who", "play", "world" and "story" from the start; the Chinese half
           # had one narrow form of "where" and no word for "who" at all.
           "哪里", "哪儿", "什么地方", "流向", "谁", "玩", "故事", "冒险", "世界",
           # Movement, for the same reason as the English list: the second rung
           # is a choice between two things a character might be doing, and a
           # Chinese rung says 走开 or 飞走 rather than 发生.
           "走", "飞", "跑", "游", "回来", "过来", "出去", "睡", "等", "找"),
}

# The sketch entrance asks about the process rather than the world, because a
# plaster cast has no story: which part changed most, where the difficulty was,
# what was tried. Settled with the operator.
# Widened for the same reason as WORLD_MARKERS: a live run failed
# "What part of the cast did you redraw the most?", which is section 5a's own
# sketch question in the model's words. The list carried "which part" but not
# "what part", and "redo" but not "redraw".
# Widened again the same day, from a second sweep: "how did you" is the opener
# the model reaches for most often when asked about process, and three questions
# were failed for using it — how did you decide on the placement, how did you
# approach drawing the cast, how did you decide on the texture direction.
# And widened on the Chinese side, from the first Chinese run: two of
# six sketch questions were failed for not asking about process while containing
# the word "process" and the word "method" respectively. The Chinese list had
# been written from the English one's early shape and never revisited, so it
# carried the concrete verbs — erase, redraw, measure — and none of the abstract
# ones a model actually reaches for: process, method, adjust, handle, observe.
PROCESS_MARKERS = {
    "en": ("which part", "what part", "hardest", "hard", "difficult", "trouble",
           "changed", "change", "tried", "try", "how many times", "start", "measure",
           "erase", "redo", "redraw", "redrew", "the most", "first", "again",
           "how did you", "how do you", "decide", "approach"),
    "zh": ("哪一块", "哪里", "哪儿", "哪个", "哪一", "哪部分", "最难", "难",
           "改了", "改过", "修改", "试了", "试过", "几次", "从哪", "量一量", "量了",
           "擦", "重画", "最多", "先画", "怎么画", "过程", "方法", "步骤",
           "调整", "处理", "观察", "反复"),
}

# Words too common to count as an echo of anything a child actually said.
ECHO_STOPWORDS = frozenset({
    "the", "a", "an", "is", "it", "and", "to", "of", "in", "on", "at", "that",
    "this", "you", "your", "i", "was", "were", "are", "he", "she", "they", "so",
    "but", "for", "with", "his", "her", "its", "my", "me", "we", "as", "be",
})
