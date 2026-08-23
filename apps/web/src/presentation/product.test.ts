import { describe, expect, it } from "vitest";
import {
  presentBoolean,
  presentCheckpointRole,
  presentCostStatus,
  presentHealthStatus,
  presentIdentityRole,
  presentRuntimePhase,
} from "./product";

describe("product presentation", () => {
  it("localizes runtime and identity values", () => {
    expect(presentIdentityRole("Authenticated", "it")).toBe("Autenticato");
    expect(presentRuntimePhase("synthesis", "it")).toBe("Sintesi");
    expect(presentCheckpointRole("worker_execution_snapshot", "en")).toBe("Durable worker snapshot");
  });

  it("keeps cost, health, and booleans human-readable", () => {
    expect(presentCostStatus("unknown", "it")).toBe("Sconosciuto");
    expect(presentHealthStatus("authentication_required", "en")).toBe("Sign-in required");
    expect(presentBoolean(true, "it")).toBe("Sì");
  });

  it("does not expose unknown internal enum values", () => {
    expect(presentRuntimePhase("future_internal_phase", "it")).toBe("Non disponibile");
  });
});
