#include "StdAfx.h"
#include "PaletteSnapshotProvider.h"

#include <cstdlib>
#include <cctype>
#include <filesystem>
#include <fstream>

using namespace RigCalc;

namespace
{
	std::string ActiveDocumentPath()
	{
		using namespace VectorWorks::Filing;
		IFileIdentifierPtr file(IID_FileIdentifier);
		bool saved = false;
		if (!gSDK->GetActiveDocument(&file, saved) || !saved || !file) return {};
		TXString path;
		if (file->GetFileFullPath(path) != kVCOMError_NoError) return {};
		return path.GetStdString();
	}

	std::string SnapshotPath()
	{
		const std::string documentPath = ActiveDocumentPath();
		if (documentPath.empty()) return {};
		std::filesystem::path root(documentPath);
		root.replace_extension(".rigcalc");
		return (root / "latest" / "rigcalc_palette.json").string();
	}

	std::string SettingsPath()
	{
		const char* appData = std::getenv("APPDATA");
		if (!appData) return {};
		return std::string(appData) +
			"\\Nemetschek\\Vectorworks\\2027\\RigCalc\\pending_settings.json";
	}

	std::string RunRequestPath()
	{
		const char* appData = std::getenv("APPDATA");
		if (!appData) return {};
		return std::string(appData) +
			"\\Nemetschek\\Vectorworks\\2027\\RigCalc\\run_request.json";
	}

	std::string Fold(std::string value)
	{
		for (char& character : value) character = static_cast<char>(
			std::tolower(static_cast<unsigned char>(character)));
		return value;
	}

	bool DrawingIsNewerThanSnapshot()
	{
		try {
			const std::string documentPath = ActiveDocumentPath();
			const std::string snapshotPath = SnapshotPath();
			return !documentPath.empty() && std::filesystem::exists(snapshotPath) &&
				std::filesystem::last_write_time(documentPath) >
				std::filesystem::last_write_time(snapshotPath);
		}
		catch (const std::filesystem::filesystem_error&) { return false; }
	}
}

CPaletteSnapshotProvider::CPaletteSnapshotProvider(IVWUnknown* parent)
	: VWExtensionPaletteJSProvider(parent)
{
}

void VCOM_CALLTYPE CPaletteSnapshotProvider::OnInit(IInitContext* context)
{
	VWExtensionPaletteJSProvider::OnInit(context);
	context->AddFunctionPromiseSync("RigCalcBridge.getSnapshot");
	context->AddFunctionPromiseSync("RigCalcBridge.calculate");
	context->AddFunctionPromiseSync("RigCalcBridge.saveSettings");
	context->AddFunctionPromiseSync("RigCalcBridge.showObject");
	context->AddFunctionPromiseSync("RigCalcBridge.renameHoist");
}

BEGIN_WebPalette_DISPATCH_MAP(CPaletteSnapshotProvider)
	ADD_WebPalette_FUNCTION("getSnapshot", GetSnapshot)
	ADD_WebPalette_FUNCTION("calculate", Calculate)
	ADD_WebPalette_FUNCTION("saveSettings", SaveSettings)
	ADD_WebPalette_FUNCTION("showObject", ShowObject)
	ADD_WebPalette_FUNCTION("renameHoist", RenameHoist)
END_WebPalette_DISPATCH_MAP2

void CPaletteSnapshotProvider::GetSnapshot(
	const TXString&, const TXString&, const std::vector<nlohmann::json>&,
	VectorWorks::UI::IJSFunctionCallbackContext* context)
{
	std::ifstream stream(SnapshotPath());
	if (!stream.is_open()) {
		if (ActiveDocumentPath().empty()) {
			context->Reject("Save and activate a Vectorworks drawing before loading RigCalc results.");
		}
		else {
			context->Reject("No RigCalc result is available for the active drawing. Run RigCalc first.");
		}
		return;
	}

	nlohmann::json snapshot;
	try {
		stream >> snapshot;
		if (!snapshot.is_object() || snapshot.value("schema_version", 0) != 1) {
			context->Reject("RigCalc result has an unsupported snapshot format.");
			return;
		}
		const std::string snapshotDocument = snapshot.value(
			"document", nlohmann::json::object()).value("path", "");
		if (snapshotDocument != ActiveDocumentPath()) {
			context->Reject("RigCalc result belongs to a different drawing and was not loaded.");
			return;
		}
		// File modification time catches saved drawing edits made after the run.
		// The palette also marks edits made through RenameHoist immediately.
		const bool stale = snapshot.value("drawing_state", nlohmann::json::object()).value(
			"stale", false) || DrawingIsNewerThanSnapshot();
		snapshot["drawing_state"] = {
			{"stale", stale},
			{"message", stale
				? "Drawing changed since this calculation. Run again."
				: "The result matches the most recently saved drawing."}
		};
		context->Resolve(snapshot);
	}
	catch (const std::exception&) {
		context->Reject("RigCalc result could not be read.");
	}
}

void CPaletteSnapshotProvider::RenameHoist(
	const TXString&, const TXString&, const std::vector<nlohmann::json>& args,
	VectorWorks::UI::IJSFunctionCallbackContext* context)
{
	if (args.empty() || !args[0].is_object()) {
		context->Reject("Motor ID and motor UUID are missing."); return;
	}
	const auto& request = args[0];
	const std::string uuid = request.value("object_uuid", "");
	const std::string objectId = request.value("object_id", "");
	const std::string identifier = request.value("hoist_id", "");
	const std::string system = request.value("truss_system", "");
	if (uuid.empty() || identifier.empty()) {
		context->Reject("Motor ID cannot be empty."); return;
	}
	if (DrawingIsNewerThanSnapshot()) {
		context->Reject("The drawing has changed since this result. Run RigCalc again before editing a motor ID."); return;
	}
	std::ifstream stream(SnapshotPath());
	nlohmann::json snapshot;
	try { stream >> snapshot; }
	catch (const std::exception&) { context->Reject("Could not validate existing motor IDs."); return; }
	for (const auto& hoist : snapshot.value("hoists", nlohmann::json::array())) {
		if (hoist.value("object_id", "") != objectId &&
			Fold(hoist.value("truss_system_name", "")) == Fold(system) &&
			Fold(hoist.value("hoist_id", "")) == Fold(identifier)) {
			context->Reject("Motor ID already exists in this truss system."); return;
		}
	}
	MCObjectHandle object = gSDK->GetObjectByUuid(TXString(uuid));
	if (!object) { context->Reject("This motor no longer exists in the active drawing."); return; }
	VWParametricObj hoist(object);
	hoist.SetParamString("HoistID", TXString(identifier));
	gSDK->ResetObject(object);
	// Preserve calculated values, but persist that this result cannot be used
	// for the modified drawing. A calculation is the only source of fresh data.
	snapshot["drawing_state"] = {
		{"stale", true},
		{"message", "Drawing changed since this calculation. Run again."}
	};
	std::ofstream staleSnapshot(SnapshotPath(), std::ios::trunc);
	if (!staleSnapshot.is_open()) {
		context->Reject("Motor ID was changed, but the result could not be marked as outdated."); return;
	}
	staleSnapshot << snapshot.dump(2);
	context->Resolve(nlohmann::json{{"hoist_id", identifier}, {"drawing_changed", true}});
}

void CPaletteSnapshotProvider::ShowObject(
	const TXString&, const TXString&, const std::vector<nlohmann::json>& args,
	VectorWorks::UI::IJSFunctionCallbackContext* context)
{
	if (args.empty() || !args[0].is_string()) { context->Reject("Motor UUID is missing."); return; }
	const TXString uuid(args[0].get<std::string>());
	MCObjectHandle object = gSDK->GetObjectByUuid(uuid);
	if (!object) { context->Reject("This motor no longer exists in the active drawing."); return; }
	gSDK->ShowAndSelectObject(object);
	context->Resolve(nlohmann::json{{"selected", true}});
}

void CPaletteSnapshotProvider::SaveSettings(
	const TXString&, const TXString&, const std::vector<nlohmann::json>& args,
	VectorWorks::UI::IJSFunctionCallbackContext* context)
{
	if (args.empty() || !args[0].is_object()) {
		context->Reject("Calculation settings are missing.");
		return;
	}
	const auto& settings = args[0];
	const double cableLoad = settings.value("cable_load_kg_m", -1.0);
	const double safetyFactor = settings.value("safety_factor", 0.0);
	if (cableLoad < 0.0 || safetyFactor <= 0.0) {
		context->Reject("Cable load must be zero or higher, and factor must be positive.");
		return;
	}
	std::ofstream stream(SettingsPath(), std::ios::trunc);
	if (!stream.is_open()) {
		context->Reject("RigCalc settings could not be saved.");
		return;
	}
	const nlohmann::json stored = {
		{"cable_load_kg_m", cableLoad}, {"safety_factor", safetyFactor}};
	stream << stored.dump(2);
	context->Resolve(stored);
}

void CPaletteSnapshotProvider::Calculate(
	const TXString&, const TXString&, const std::vector<nlohmann::json>&,
	VectorWorks::UI::IJSFunctionCallbackContext* context)
{
	// This is the existing script-plugin's universal menu name. It preserves
	// the same validated Python command path as running RigCalc from a menu.
	const std::string requestPath = RunRequestPath();
	std::filesystem::create_directories(std::filesystem::path(requestPath).parent_path());
	std::ofstream request(requestPath, std::ios::trunc);
	if (!request.is_open()) {
		context->Reject("RigCalc run request could not be saved.");
		return;
	}
	request << nlohmann::json{{"run_from_palette", true}}.dump();
	request.close();
	// DoMenuName returns zero for a successfully dispatched script command in
	// this host version. The completed snapshot is the authoritative outcome.
	gSDK->DoMenuName("RigCalc", 0);
	context->Resolve(nlohmann::json{{"started", true}});
}
