import { Logger } from "@nestjs/common";

// Unit tests assert on state, not on log lines — keep the output readable.
Logger.overrideLogger(false);
