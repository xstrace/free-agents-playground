export default function (pi: ExtensionAPI) {
  pi.registerProvider("opencode", {
    baseUrl: "http://fap-gateway:8787/v1",
    apiKey: "local-gateway",
  });
}
