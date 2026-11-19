#pragma once

namespace RigCalc
{
	using namespace VWFC::PluginSupport;

	class CPaletteSnapshotProvider : public VWExtensionPaletteJSProvider
	{
	public:
		explicit CPaletteSnapshotProvider(IVWUnknown* parent);
		virtual void VCOM_CALLTYPE OnInit(IInitContext* context) override;
		DEFINE_WebPalette_DISPATCH_MAP;

	private:
		void GetSnapshot(const TXString& objectName, const TXString& functionName,
			const std::vector<nlohmann::json>& args,
			VectorWorks::UI::IJSFunctionCallbackContext* context);
		void Calculate(const TXString& objectName, const TXString& functionName,
			const std::vector<nlohmann::json>& args,
			VectorWorks::UI::IJSFunctionCallbackContext* context);
		void SaveSettings(const TXString& objectName, const TXString& functionName,
			const std::vector<nlohmann::json>& args,
			VectorWorks::UI::IJSFunctionCallbackContext* context);
		void ShowObject(const TXString& objectName, const TXString& functionName,
			const std::vector<nlohmann::json>& args,
			VectorWorks::UI::IJSFunctionCallbackContext* context);
		void RenameHoist(const TXString& objectName, const TXString& functionName,
			const std::vector<nlohmann::json>& args,
			VectorWorks::UI::IJSFunctionCallbackContext* context);
	};
}
