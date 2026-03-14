using System;
using System.Text.Json;

namespace AIDirector.UnityRuntime
{
    public static class DirectorJsonUtility
    {
        private static readonly JsonSerializerOptions Options = new JsonSerializerOptions
        {
            IncludeFields = true,
            WriteIndented = true
        };

        [Serializable]
        private class Wrapper<T>
        {
            public T[] items;
        }

        public static string ToJson<T>(T value, bool prettyPrint = true)
        {
            if (prettyPrint)
            {
                return JsonSerializer.Serialize(value, Options);
            }

            return JsonSerializer.Serialize(value, new JsonSerializerOptions
            {
                IncludeFields = true,
                WriteIndented = false
            });
        }

        public static T FromJson<T>(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                return default;
            }

            return JsonSerializer.Deserialize<T>(json, Options);
        }

        public static T[] FromJsonArray<T>(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                return Array.Empty<T>();
            }

            var wrappedJson = "{\"items\":" + json + "}";
            var wrapper = UnityEngine.JsonUtility.FromJson<Wrapper<T>>(wrappedJson);
            return wrapper != null && wrapper.items != null ? wrapper.items : Array.Empty<T>();
        }
    }
}
