using System.Text.Json;
using System.Text.Json.Serialization;

namespace TaskHarness.Core;

public static class HarnessStatus
{
    public const string Pending = "pending";
    public const string Active = "active";
    public const string EvidenceReady = "evidence_ready";
    public const string Passed = "passed";
    public const string Blocked = "blocked";
    public const string Regressed = "regressed";

    public static readonly string[] All =
    {
        Pending, Active, EvidenceReady, Passed, Blocked, Regressed
    };

    public static readonly IReadOnlyDictionary<string, string> Labels = new Dictionary<string, string>
    {
        [Pending] = "待处理",
        [Active] = "进行中",
        [EvidenceReady] = "待独立评审",
        [Passed] = "已通过",
        [Blocked] = "已阻塞",
        [Regressed] = "需回归"
    };

    public static readonly IReadOnlyDictionary<string, string> Means = new Dictionary<string, string>
    {
        [Pending] = "还没开始",
        [Active] = "正在做，还没交",
        [EvidenceReady] = "做完了，但还没有独立评审确认",
        [Passed] = "独立评审通过 —— 只有这个状态能叫完成",
        [Blocked] = "卡住了（原因记在任务里）",
        [Regressed] = "曾经通过，但因依赖/接口变更失效，需要重做"
    };

    public static readonly IReadOnlyDictionary<string, double> Fill = new Dictionary<string, double>
    {
        [Pending] = 8,
        [Active] = 42,
        [EvidenceReady] = 78,
        [Passed] = 100,
        [Blocked] = 28,
        [Regressed] = 55
    };

    public static bool IsKnown(string? status) => status is not null && Labels.ContainsKey(status);
}

public sealed class TaskFile
{
    [JsonPropertyName("project")]
    public string? Project { get; set; }

    [JsonPropertyName("rev")]
    public JsonElement? Rev { get; set; }

    [JsonPropertyName("tasks")]
    public List<TaskItem> Tasks { get; set; } = new();
}

public sealed class TaskItem
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = "";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "";

    [JsonPropertyName("desc")]
    public string? Desc { get; set; }

    [JsonPropertyName("description")]
    public string? Description { get; set; }

    [JsonPropertyName("depends_on")]
    public List<string>? DependsOn { get; set; }

    [JsonPropertyName("priority")]
    public double? Priority { get; set; }

    [JsonPropertyName("verify")]
    public string? Verify { get; set; }

    [JsonPropertyName("reason")]
    public JsonElement? Reason { get; set; }

    [JsonPropertyName("wave")]
    public string? Wave { get; set; }

    [JsonPropertyName("phase")]
    public JsonElement? Phase { get; set; }

    public string DisplayDesc =>
        string.IsNullOrWhiteSpace(Desc)
            ? (string.IsNullOrWhiteSpace(Description) ? "未填写" : Description!)
            : Desc!;

    public IReadOnlyList<string> Deps => DependsOn ?? (IReadOnlyList<string>)Array.Empty<string>();

    public string ReasonText
    {
        get
        {
            if (Reason is null || Reason.Value.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
                return "";
            return Reason.Value.ValueKind == JsonValueKind.String
                ? Reason.Value.GetString() ?? ""
                : Reason.Value.GetRawText();
        }
    }
}

public sealed class JsonlRow
{
    public Dictionary<string, JsonElement> Fields { get; init; } = new();

    public string? Str(string key) =>
        Fields.TryGetValue(key, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

    public JsonElement? El(string key) => Fields.TryGetValue(key, out var v) ? v : null;
}

public sealed class BoardMap
{
    public string? Where { get; init; }
    public IReadOnlyList<BoardNext> Next { get; init; } = Array.Empty<BoardNext>();
}

public sealed class BoardNext
{
    public string Task { get; init; } = "";
    public string? Why { get; init; }
    public string? See { get; init; }
}

public sealed class HarnessSnapshot
{
    public string Path { get; set; } = "";
    public TaskFile Tasks { get; init; } = new();
    public IReadOnlyList<JsonlRow> Evidence { get; init; } = Array.Empty<JsonlRow>();
    public IReadOnlyList<JsonlRow> Reviews { get; init; } = Array.Empty<JsonlRow>();
    public string Progress { get; init; } = "";
    public BoardMap? Board { get; init; }
}
