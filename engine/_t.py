import sys; sys.path.insert(0, 'engine')
import compose_lab
p = {'scenes': [{'type': 'title', 'big': 'KAISE HOTA HAI', 'sub': 'x', 'vo': 'a b c'},
                {'type': 'chat', 'title': 'ChatGPT', 'messages': [{'role': 'user', 'text': 'Capital of India?'}, {'role': 'ai', 'text': 'New Delhi is the capital of India.'}], 'vo': 'd e f', 'label': 'DEMO'},
                {'type': 'code', 'lines': ['pip install x', 'python run.py'], 'highlight': 1, 'vo': 'g h', 'label': 'CODE'},
                {'type': 'ui', 'title': 'T', 'rows': [{'label': 'a', 'value': '1', 'pct': 50}], 'vo': 'i j'}]}
t = [{'start': i * 3.0, 'end': i * 3 + 2.5, 'words': [{'w': 'a', 's': i * 3.0, 'e': i * 3 + 0.5}]} for i in range(4)]
doc, c = compose_lab.page(p, t, 14.0, {'accent': '#f5c542', 'accent2': '#46d1ff', 'handle': '@kaise.tech', 'lang': 'hi'}, {})
print(len(doc), doc.count('class="bub'), doc.count('class="tl'), 'uline' in doc, 'shine' in doc)
open(sys.argv[1] if len(sys.argv) > 1 else 'test.html', 'w', encoding='utf-8').write(doc)
