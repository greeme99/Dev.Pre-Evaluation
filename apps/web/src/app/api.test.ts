import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

describe("workflow API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("creates projects with the JSON request contract", async () => {
    const project = {
      id: "project-1",
      name: "공정 검토",
      created_at: "2026-10-21T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(project), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.createProject({ name: project.name })).resolves.toEqual(project);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/projects",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ name: project.name }),
      }),
    );
    expect(new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("Content-Type")).toBe(
      "application/json",
    );
  });

  it("uploads a drawing as multipart without setting its boundary header", async () => {
    const drawing = {
      id: "drawing-1",
      project_id: "project-1",
      sha256: "a".repeat(64),
      drawing_type: "dxf",
      source_name: "drawing.dxf",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(drawing), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["0\nSECTION\n"], "drawing.dxf", { type: "application/dxf" });

    await expect(api.uploadDrawing("project-1", file)).resolves.toEqual(drawing);

    const [url, options] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe("/api/projects/project-1/drawings");
    expect(options?.method).toBe("POST");
    expect(options?.body).toBeInstanceOf(FormData);
    expect((options?.body as FormData).get("file")).toBe(file);
    expect(new Headers(options?.headers).has("Content-Type")).toBe(false);
  });
});
