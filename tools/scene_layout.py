# -*- coding: utf-8 -*-
"""把场景方案编译成 Layout 提示词。

    python3 tools/scene_layout.py plans/spray.json --width 896 --height 1200
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from photocraft_draw.scene_prompt import caption_from_plan, layout_from_plan

SKILL = Path("/home/wanli/cb-cwd-20261007/.codebuddy/skills/moss-image-prompt-enhancer")
COMPILER = SKILL / "scripts/compile_prompt.py"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="场景方案转 Layout 提示词")
    parser.add_argument("plan")
    parser.add_argument("--width", type=int, default=896)
    parser.add_argument("--height", type=int, default=1200)
    parser.add_argument("--out", default="out/spray-layout.json")
    args = parser.parse_args(argv)

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    draft = layout_from_plan(plan, args.width, args.height, caption_from_plan(plan))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    target = out.with_name(out.stem + "-prompt.txt")
    result = subprocess.run([sys.executable, str(COMPILER), str(out), "--output", str(target)],
                            capture_output=True, text=True)
    print(result.stdout.strip() or result.stderr.strip())
    if result.returncode:
        return result.returncode
    print("草稿：%s" % out)
    print("提示词：%s" % target)
    print(target.read_text(encoding="utf-8")[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
