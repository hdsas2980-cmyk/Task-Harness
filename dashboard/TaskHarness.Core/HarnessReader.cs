using System.Text;
using System.Text.Json;

namespace TaskHarness.Core;

public static class HarnessReader
{
    public static readonly string[] OptionalFiles = { "evidence.jsonl", "reviews.jsonl", "progress.txt", "board.json" };

    static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = false
    };

    public static bool HasTasks(string path) =>
        File.Exists(Path.Combine(path, "tasks.json"))
        || File.Exists(Path.Combine(path, ".harness", "tasks.json"));

    public static string ResolveSource(string path)
    {
        var dir = Path.GetFullPath(path);
        if (string.Equals(Path.GetFileName(dir), ".harness", StringComparison.OrdinalIgnoreCase))
            return dir;
        var nested = Path.Combine(dir, ".harness");
        if (File.Exists(Path.Combine(nested, "tasks.json")) || !File.Exists(Path.Combine(dir, "tasks.json")))
            return nested;
        return dir;
    }

    public static IEnumerable<string> ProbeCandidates(string? cwd = null, string? exeDir = null)
    {
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var raw in new[] { cwd, exeDir })
        {
            if (string.IsNullOrWhiteSpace(raw)) continue;
            var full = Path.GetFullPath(raw);
            if (seen.Add(full)) yield return full;
        }
    }

    public static HarnessSnapshot Load(string path)
    {
        var source = ResolveSource(path);
        var tasksPath = Path.Combine(source, "tasks.json");
        if (!File.Exists(tasksPath))
            throw new InvalidDataException("该目录没有 tasks.json: " + source);

        var texts = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["tasks.json"] = ReadText(tasksPath)
        };
        foreach (var name in OptionalFiles)
        {
            var file = Path.Combine(source, name);
            if (File.Exists(file))
                texts[name] = ReadText(file);
        }
        var parsed = Parse(texts);
        parsed.Path = source;
        return parsed;
    }

    public static HarnessSnapshot Parse(IReadOnlyDictionary<string, string> texts)
    {
        if (!texts.ContainsKey("tasks.json"))
            throw new InvalidDataException("缺少任务文件；原任务保持不变");
        TaskFile tasks;
        try
        {
            tasks = JsonSerializer.Deserialize<TaskFile>(StripBom(texts["tasks.json"]), JsonOptions)
                    ?? throw new InvalidDataException("任务文件必须包含任务数组");
        }
        catch (JsonException)
        {
            throw new InvalidDataException("任务文件格式错误；原任务保持不变");
        }
        if (tasks.Tasks is null)
            throw new InvalidDataException("任务文件必须包含任务数组");

        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var t in tasks.Tasks)
        {
            if (t is null || string.IsNullOrWhiteSpace(t.Id) || !ids.Add(t.Id))
                throw new InvalidDataException("任务编号缺失或重复");
            if (!HarnessStatus.IsKnown(t.Status))
                throw new InvalidDataException("任务包含未知状态");
            if (t.DependsOn is not null && t.DependsOn.Any(d => d is null))
                throw new InvalidDataException("任务依赖必须是编号数组");
        }

        return new HarnessSnapshot
        {
            Tasks = tasks,
            Evidence = ParseJsonl(texts.TryGetValue("evidence.jsonl", out var ev) ? ev : "", "证据"),
            Reviews = ParseJsonl(texts.TryGetValue("reviews.jsonl", out var rv) ? rv : "", "评审"),
            Progress = texts.TryGetValue("progress.txt", out var pg) ? pg : "",
            Board = ParseBoard(texts.TryGetValue("board.json", out var board) ? board : "")
        };
    }

    static List<JsonlRow> ParseJsonl(string raw, string label)
    {
        var rows = new List<JsonlRow>();
        var text = StripBom(raw);
        var lines = text.Split(new[] { "\r\n", "\n" }, StringSplitOptions.None);
        for (var i = 0; i < lines.Length; i++)
        {
            var line = lines[i];
            if (string.IsNullOrWhiteSpace(line)) continue;
            try
            {
                using var doc = JsonDocument.Parse(line);
                if (doc.RootElement.ValueKind != JsonValueKind.Object)
                    throw new JsonException();
                var fields = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
                foreach (var p in doc.RootElement.EnumerateObject())
                    fields[p.Name] = p.Value.Clone();
                rows.Add(new JsonlRow { Fields = fields });
            }
            catch (JsonException)
            {
                throw new InvalidDataException(label + "文件第 " + (i + 1) + " 行格式错误");
            }
        }
        return rows;
    }

    static BoardMap? ParseBoard(string raw)
    {
        try
        {
            using var doc = JsonDocument.Parse(string.IsNullOrWhiteSpace(raw) ? "null" : StripBom(raw));
            if (doc.RootElement.ValueKind != JsonValueKind.Object) return null;
            string? where = doc.RootElement.TryGetProperty("where", out var w) && w.ValueKind == JsonValueKind.String
                ? w.GetString() : null;
            var next = new List<BoardNext>();
            if (doc.RootElement.TryGetProperty("next", out var n) && n.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in n.EnumerateArray())
                {
                    if (item.ValueKind != JsonValueKind.Object) continue;
                    next.Add(new BoardNext
                    {
                        Task = item.TryGetProperty("task", out var t) && t.ValueKind == JsonValueKind.String ? t.GetString() ?? "" : "",
                        Why = item.TryGetProperty("why", out var why) && why.ValueKind == JsonValueKind.String ? why.GetString() : null,
                        See = item.TryGetProperty("see", out var see) && see.ValueKind == JsonValueKind.String ? see.GetString() : null
                    });
                }
            }
            if (string.IsNullOrWhiteSpace(where) && next.Count == 0) return null;
            return new BoardMap { Where = where, Next = next };
        }
        catch (JsonException)
        {
            return null;
        }
    }

    static string ReadText(string path) => File.ReadAllText(path, Encoding.UTF8);

    static string StripBom(string text) => text.Length > 0 && text[0] == '\uFEFF' ? text[1..] : text;
}
