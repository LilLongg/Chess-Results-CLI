def main():
    import argparse
    from collections import defaultdict
    from io import BytesIO
    from heapq import nlargest
    import pandas as pd
    import re
    import requests
    import sys

    # Parsing command-line arguments
    args_parser = argparse.ArgumentParser(
        description="Xác định các giải cá nhân, đồng đội và toàn đoàn của một giải đấu được lưu trên chess-results.com",
        add_help=True,
        allow_abbrev=False,
    )
    args_parser._actions[
        0
    ].help = "Miêu tả hướng dẫn sử dụng của chương trình và thoát."
    args_parser.add_argument(
        "INPUT",
        help="Các đường link đến giải đấu hoặc đường dẫn đến file excel lưu kết quả giải đấu.",
        type=str,
        nargs="+",
    )
    args_parser.add_argument(
        "-o",
        "--output",
        help="Đường dẫn đến file excel lưu kết quả chương trình (mặc định là in ra màn hình).",
        type=str,
    )
    args_parser.add_argument(
        "-e", "--exclude", help="Lược bỏ các đội/đoàn.", type=str, nargs="+"
    )
    args = args_parser.parse_args(args=None if sys.argv[1:] else ["-h"])
    INPUT_PATH: list[str] = args.INPUT
    OUTPUT_PATH: str | None = args.output
    EXCLUDED: list[str] = args.exclude or []
    LINK_REGEX = re.compile(r"https://chess-results.com/tnr\d+.aspx")

    # Reading tournament results
    def get_tournament_results(PATH: str) -> pd.DataFrame:
        if PATH.endswith(".xlsx"):
            print(f"Đọc thông tin từ file {PATH}")
            try:
                excel = pd.read_excel(PATH)
            except FileNotFoundError:
                print(f"Không tìm thấy file {PATH}")
                exit(1)
        else:
            match_result = LINK_REGEX.match(PATH)
            if not match_result:
                print(f"Đường dẫn không hợp lệ: {PATH}")
                exit(1)

            print(f"Lấy thông tin từ đường dẫn: {PATH}")
            info = requests.get(
                f"{match_result.group(0)}?lan=1&zeilen=0&art=1&rd=-1&turdet=YES&prt=4&excel=2010",
                stream=True,
            )
            stream = BytesIO(info.content)
            excel = pd.read_excel(stream)

        # Putting the tournament results into dataframe
        TITLE = excel.iloc[0, 0]
        print(f"Đọc thông tin của giải: {TITLE}")

        df = excel[4:].rename(columns=excel.iloc[3])
        FED_KEY = "FED" if "FED" in df.columns else "Club/City"

        df["Rk."] = df["Rk."].ffill()
        df = df[["Rk.", FED_KEY, "Pts. "]].dropna()

        groups = df.groupby([FED_KEY])
        team_res = [
            (group[1]["Rk."].head(3).sum(), group[0][0])
            for group in groups
            if group[1]["Rk."].count() > 2 and group[0][0] not in EXCLUDED
        ]
        team_res = sorted(
            team_res,
            key=lambda x: (
                x[0],
                -df["Pts. "][df[FED_KEY] == x[1]].sum(),
                df["Rk."][df[FED_KEY] == x[1]].min(),
            ),
        )

        res = pd.DataFrame(
            [[fed, team[1]] for fed, team in zip(df[FED_KEY][:3], team_res[:3])],
            columns=[(TITLE, "Cá nhân"), (TITLE, "Đồng đội")],
            index=["Nhất", "Nhì", "Ba"],
        )
        res.columns = pd.MultiIndex.from_tuples(res.columns, names=["Giải", "Thể thức"])
        return res

    result_df = None
    result_pts: defaultdict[str, int] = defaultdict(int)

    for PATH in INPUT_PATH:
        result = get_tournament_results(PATH)
        if result_df is None:
            result_df = result
        else:
            result_df = pd.merge(result_df, result, left_index=True, right_index=True)

        result_pts[result.iloc[0, 0]] += 10
        result_pts[result.iloc[0, 1]] += 30
        result_pts[result.iloc[1, 0]] += 6
        result_pts[result.iloc[1, 1]] += 18
        result_pts[result.iloc[2, 0]] += 4
        result_pts[result.iloc[2, 1]] += 12

    result_df = pd.merge(
        result_df,
        pd.DataFrame(
            nlargest(3, result_pts, result_pts.get),
            columns=pd.MultiIndex.from_tuples([("Giải toàn đoàn", " ")]),
            index=["Nhất", "Nhì", "Ba"],
        ),
        left_index=True,
        right_index=True,
    )

    if OUTPUT_PATH is None:
        print(result_df)
        exit(0)

    if OUTPUT_PATH.endswith(".csv"):
        result_df.to_csv(OUTPUT_PATH)
        exit(0)

    if OUTPUT_PATH.endswith(".xlsx"):
        result_df.to_excel(OUTPUT_PATH)
        exit(0)

    if OUTPUT_PATH.endswith(".html"):
        result_df.to_html(OUTPUT_PATH)
        exit(0)

    if OUTPUT_PATH.endswith(".json"):
        with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
            result_df.to_json(file, indent=4, force_ascii=False)
        exit(0)

    print(f"Loại file này không được hỗ trợ: {OUTPUT_PATH}")
    exit(1)
