#!/usr/bin/env python3
"""snake.py — 狂野贪吃蛇 · AI 自玩观赏模式

用法:
  python3 snake.py              # curses 观赏模式(需 tty)
  python3 snake.py --sim 500    # 无界面模拟 500 步, 报告 AI 战绩
AI 是贪婪算法: 朝食物走, 撞墙/撞自己前会尝试转向, 全堵则硬闯。
"""
import curses
import random
import sys
import time
from collections import deque


MOTTOES = {
    "eat": "吃到食物前先确认退路——贪心是死因, 谨慎是活路。",
    "chase": "追不到食物, 就追自己的尾巴: 得不到想要的, 就守住已有的。",
    "escape": "给未来留一条路的人, 永远不会被困死。",
    "brave": "当所有方向都危险时, 勇敢是唯一的方向。",
    "dead": "死不是终点, 是下一轮重生的起跑线。",
}


def bfs_full(snake, target, h, w, ignore_tail=False, body=None):
    """BFS 寻路(int 坐标加速), 返回从蛇头下一格到 target 的完整路径(tuple);
    不可达返回 None。ignore_tail=True 时蛇尾视为可通过(它正在让位)。
    body 约定: int set(y*w+x), 或 None(内部从 snake 构建)。"""
    head = snake[0]
    hi = head[0] * w + head[1]
    b = set(body) if body is not None else {y * w + x for y, x in snake}
    if ignore_tail and len(snake) > 1:
        b.discard(snake[-1][0] * w + snake[-1][1])
    ti = target[0] * w + target[1]
    parent = {hi: -1}
    visited = [False] * (h * w)
    visited[hi] = True
    q = [hi]
    qi = 0
    last_row = (h - 1) * w
    while qi < len(q):
        cur = q[qi]
        qi += 1
        if cur == ti:
            path = []
            while cur != hi:
                path.append((cur // w, cur % w))
                cur = parent[cur]
            return path[::-1]
        # 邻居顺序必须保持 (右,左,下,上) 与旧版一致
        up, down, left, right = cur - w, cur + w, cur - 1, cur + 1
        if right % w != w - 1 and not visited[right] and right not in b:
            visited[right] = True
            parent[right] = cur
            q.append(right)
        if left % w != 0 and not visited[left] and left not in b:
            visited[left] = True
            parent[left] = cur
            q.append(left)
        if down < last_row and not visited[down] and down not in b:
            visited[down] = True
            parent[down] = cur
            q.append(down)
        if up >= w and not visited[up] and up not in b:
            visited[up] = True
            parent[up] = cur
            q.append(up)
    return None


def can_reach(start, goal, body, h, w):
    """start 能否在不碰 body(int set) 的情况下到 goal。"""
    si = start[0] * w + start[1]
    gi = goal[0] * w + goal[1]
    if si == gi:
        return True
    visited = [False] * (h * w)
    visited[si] = True
    q = [si]
    qi = 0
    last_row = (h - 1) * w
    while qi < len(q):
        cur = q[qi]
        qi += 1
        up, down, left, right = cur - w, cur + w, cur - 1, cur + 1
        if right % w != w - 1:
            if right == gi:
                return True
            if not visited[right] and right not in body:
                visited[right] = True
                q.append(right)
        if left % w != 0:
            if left == gi:
                return True
            if not visited[left] and left not in body:
                visited[left] = True
                q.append(left)
        if down < last_row:
            if down == gi:
                return True
            if not visited[down] and down not in body:
                visited[down] = True
                q.append(down)
        if up >= w:
            if up == gi:
                return True
            if not visited[up] and up not in body:
                visited[up] = True
                q.append(up)
    return False


def ai_dir(snake, food, h, w, body=None):
    """策略: 1) 追食物(但先验证吃完后仍能摸到尾巴, 否则不追)
              2) 追尾巴保命(能摸到尾巴=可以永远绕圈不死)
              3) 随便挑一个不立刻撞的方向"""
    head = snake[0]
    # 1) 追食物 + 逃生检查
    path = bfs_full(snake, food, h, w, body=body)
    if path:
        # 数学模拟: 走 len(path) 步(最后一步吃)。
        # 前 P-1 步不吃: 蛇身 = path[:P-1] 倒序 + 原蛇前 L-P+1 节
        # 吃完后: 头=food, 尾 = snake[L-P](P<=L) 或 path[P-L-1](P>L)
        P, L = len(path), len(snake)
        if P <= L:
            tail = snake[L - P]
            sim_body = {y * w + x for y, x in path}
            sim_body |= {y * w + x for y, x in snake[:L - P + 1]}
        else:
            # 路径比蛇身长: 蛇身是 path 的最后 L 格窗口
            tail = path[P - L - 1]
            sim_body = {y * w + x for y, x in path[P - L - 1:]}
        if can_reach(food, tail, sim_body, h, w):
            return (path[0][0] - head[0], path[0][1] - head[1])
    # 2) 追尾巴(尾巴正在让位, 视为可通过)
    path = bfs_full(snake, snake[-1], h, w, ignore_tail=True, body=body)
    if path:
        return (path[0][0] - head[0], path[0][1] - head[1])
    # 3) 硬闯
    collide = body if body is not None else {y * w + x for y, x in snake}
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nxt = (head[0] + dy, head[1] + dx)
        if 1 <= nxt[0] < h - 1 and 1 <= nxt[1] < w - 1 and (nxt[0] * w + nxt[1]) not in collide:
            return (dy, dx)
    return (0, 0)


def step(snake, food, h, w, grow, body=None):
    """推进一帧, 返回 (新蛇, 新食物或 None=吃到)。"""
    d = ai_dir(snake, food, h, w, body=body)
    head = (snake[0][0] + d[0], snake[0][1] + d[1])
    if not (1 <= head[0] < h - 1 and 1 <= head[1] < w - 1):
        return None, None
    if head == food:
        pass                      # food 必不在蛇身里, 安全
    elif body is not None:
        if (head[0] * w + head[1]) in body and head != snake[-1]:   # 尾巴让位, 可踩
            return None, None
    elif head in snake[:-1]:
        return None, None
    new = [head] + snake
    if head == food:
        return new, True          # 吃到: 不砍尾
    return new[:-1], False


def simulate(steps, h=20, w=40, seed=None):
    """纯逻辑模拟, 返回 (吃到几个, 是否存活)。"""
    if seed is not None:
        random.seed(seed)
    snake = [(h // 2, w // 2), (h // 2, w // 2 - 1), (h // 2, w // 2 - 2)]
    food = None
    eaten = 0
    body = {y * w + x for y, x in snake}
    for _ in range(steps):
        if food is None or food in snake:
            while True:
                food = (random.randint(1, h - 2), random.randint(1, w - 2))
                if food not in snake:
                    break
        old_tail = snake[-1]
        snake, got = step(snake, food, h, w, eaten, body=body)
        if snake is None:
            return eaten, False
        if got:
            eaten += 1
            body.add(snake[0][0] * w + snake[0][1])      # 吃到: 尾巴不动
        else:
            body.add(snake[0][0] * w + snake[0][1])
            body.discard(old_tail[0] * w + old_tail[1])  # 旧尾巴让位(不是新蛇的尾巴!)
    return eaten, True


def play(stdscr):
    curses.curs_set(0)
    curses.use_default_colors()
    stdscr.nodelay(1)
    stdscr.timeout(80)
    h, w = stdscr.getmaxyx()
    if w < 40 or h < 20:
        stdscr.addstr(0, 0, "窗口太小, 至少要 40x20")
        stdscr.refresh()
        time.sleep(2)
        return
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    gy, gx = 3, 2                       # 游戏区左上角
    gh, gw = h - 4, w - 4
    snake = [(gy + gh // 2, gx + gw // 2), (gy + gh // 2, gx + gw // 2 - 1)]
    food = (gy + 2, gx + 2)
    eaten = 0
    while True:
        # 边界
        stdscr.addstr(0, 0, "🐍 狂野贪吃蛇 · AI 自玩观赏模式 · q 退出", curses.A_BOLD | curses.color_pair(3))
        stdscr.addstr(1, 0, f"长度 {len(snake):>3}   吃到 {eaten}   速度 {(len(snake)//5+1)*10} fps")
        for x in range(gx, gx + gw):
            stdscr.addstr(gy, x, "─")
            stdscr.addstr(gy + gh - 1, x, "─")
        for y in range(gy, gy + gh):
            stdscr.addstr(y, gx, "│")
            stdscr.addstr(y, gx + gw - 1, "│")
        for y, x in snake:
            stdscr.addstr(y, x, "o", curses.color_pair(1))
        stdscr.addstr(snake[0][0], snake[0][1], "O", curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(food[0], food[1], "●", curses.color_pair(2))
        stdscr.refresh()
        if food in snake or (food[0] == 0):
            while True:
                food = (random.randint(gy + 1, gy + gh - 2), random.randint(gx + 1, gx + gw - 2))
                if food not in snake:
                    break
        snake, got = step(snake, food, gy + gh, gx + gw, eaten)
        if snake is None:
            stdscr.addstr(h - 2, 0, f"💥 AI 撞了!  战绩: 吃到 {eaten} 个, 长度 {eaten + 2}", curses.color_pair(2))
            stdscr.refresh()
            time.sleep(2.5)
            return
        if got:
            eaten += 1
        key = stdscr.getch()
        if key in (ord('q'), 27):
            return


def bio(h=20, w=40, steps=30000, seed=4):
    """蛇生传记: 记录成长曲线, 画 ASCII 折线图。"""
    random.seed(seed)
    snk = [(h // 2, w // 2), (h // 2, w // 2 - 1), (h // 2, w // 2 - 2)]
    food = None
    eaten = 0
    body = {y * w + x for y, x in snk}
    curve = []
    events = []
    died = None
    for n in range(steps):
        if food is None or food in snk:
            while True:
                food = (random.randint(1, h - 2), random.randint(1, w - 2))
                if food not in snk:
                    break
        snk2, got = step(snk, food, h, w, eaten, body=body)
        if snk2 is None:
            died = n
            break
        if got:
            eaten += 1
            body.add(snk2[0][0] * w + snk2[0][1])
        else:
            body.add(snk2[0][0] * w + snk2[0][1])
            body.discard(snk[-1][0] * w + snk[-1][1])
        snk = snk2
        if n % 400 == 0:
            curve.append((n, len(snk)))
        if got:
            events.append((n, eaten))
    total = died if died is not None else steps
    maxlen = max(len(snk), max((c[1] for c in curve), default=0))
    H, Wc = 12, 52
    grid = [[' '] * Wc for _ in range(H)]
    for i in range(H):
        grid[i][0] = '│'
    for i in range(Wc):
        grid[H - 1][i] = '─'
    for px, py in curve:
        x = int(px / total * (Wc - 2)) + 1
        y = H - 1 - int(py / maxlen * (H - 2))
        grid[y][x] = '●'
    print(f"🐍 蛇生传记 · seed {seed} · {h - 2}x{w - 2} 棋盘 · 采样 {total} 步")
    for row in grid:
        print(''.join(row))
    print()
    print(f"  寿命: {'∞ 仍存活' if died is None else str(died) + ' 步'} | 吃到 {eaten} 个 | 终长 {eaten + 3} 节")
    if events:
        print(f"  第一次进食: 第 {events[0][0]} 步")
    print("  格言:", MOTTOES["escape"])


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--bio":
        h = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        w = int(sys.argv[3]) if len(sys.argv) > 3 else 40
        steps = int(sys.argv[4]) if len(sys.argv) > 4 else 30000
        seed = int(sys.argv[5]) if len(sys.argv) > 5 else 4
        bio(h=h, w=w, steps=steps, seed=seed)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--arena":
        h = int(sys.argv[2])
        w = int(sys.argv[3])
        steps = int(sys.argv[4]) if len(sys.argv) > 4 else 200_000
        seeds = int(sys.argv[5]) if len(sys.argv) > 5 else 3
        inner_h, inner_w = h - 2, w - 2
        cells = inner_h * inner_w
        print(f"🏟️ 极限生存锦标赛 · 棋盘 {inner_h}x{inner_w} ({cells} 格)")
        print(f"   每种子 {steps:,} 步 · 理论食物上限 {cells - 3}")
        print("─" * 56)
        print(f"{'seed':<6}{'吃到':<8}{'终长':<8}{'步数':<10}结局")
        print("─" * 56)
        best = (0, None)
        for seed in range(1, seeds + 1):
            random.seed(seed)
            eaten, alive = simulate(steps, h=h, w=w)
            length = eaten + 3
            mark = "🏆" if eaten > best[0] else ""
            if eaten > best[0]:
                best = (eaten, seed)
            print(f"{seed:<6}{eaten:<8}{length:<8}{steps:<10}{'存活' if alive else '💥撞死'} {mark}")
        print("─" * 56)
        if best[1]:
            print(f"冠军: seed {best[1]}, 吃掉 {best[0]} 个食物, 长度 {best[0] + 3}")
            print(f"占满棋盘 {best[0] / (cells - 3) * 100:.1f}%")
            print("格言:", MOTTOES["escape"])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--sim":
        steps = int(sys.argv[2]) if len(sys.argv) > 2 else 500
        eaten, alive = simulate(steps)
        verdict = "🏆 活着" if alive else "💥 撞了"
        print(f"模拟 {steps} 步: 吃到 {eaten} 个食物, 结束时 {verdict}")
        print("格言:", MOTTOES["chase"] if alive else MOTTOES["dead"])
        return
    curses.wrapper(play)


if __name__ == "__main__":
    main()
