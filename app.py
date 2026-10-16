                            label="📄 Download Merged Profile + CV (DOCX)",
                            data=merged_docx_bytes,
                            file_name=merged_docx_name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key="download_merged_profile_cv_docx",
                        )

                        # PDF is generated independently so missing LibreOffice cannot
                        # prevent the user from downloading the successfully merged DOCX.
                        try:
                            create_merged_pdf_output(
                                profile_docx_path=Path(file_name),
                                saved_cv_path=saved_cv_path,
                                cv_suffix=cv_suffix,
                                merged_pdf_path=merged_pdf_path,
                                work_dir=merge_temp_path,
                            )
                            merged_pdf_bytes = merged_pdf_path.read_bytes()
                        except Exception as pdf_merge_error:
                            st.warning("The merged DOCX is ready, but merged PDF creation failed. Install LibreOffice on the app host to enable DOCX-to-PDF conversion.")
                            st.caption(str(pdf_merge_error))
                        else:
                            st.download_button(
                                label="📕 Download Merged Profile + CV (PDF)",
                                data=merged_pdf_bytes,
                                file_name=merged_pdf_name,
                                mime="application/pdf",
                                key="download_merged_profile_cv_pdf",
                            )
            
        except Exception as e:
            st.error("❌ Could not prepare the generated files for download.")
            st.exception(e)
            st.stop()

        # ========================================================
        # SUCCESS
        # ========================================================

        st.success(
            f"✅ Profile Generated Successfully: "
            f"{file_name}"
        )

        # ========================================================
        # FINAL SUMMARY
        # ========================================================

        st.subheader(
            "📄 Generated Profile Summary"
        )

        st.write(
            f"**File Name:** `{file_name}`"
        )

        st.write(
            f"**Candidate:** {name}"
        )

        st.write(
            f"**Contact:** {phone}"
        )

        st.write(
            f"**Email:** {email}"
        )

        st.write(
            f"**Current Location:** "
            f"{location}"
        )

        st.write(
            f"**Experience:** {exp}"
        )

        st.write(
            f"**DOB:** {dob}"
        )

        st.write(
            f"**Notice Period:** "
            f"{notice_period}"
        )

        st.write(
            f"**Interview Dates:** "
            f"{dates[0]}, "
            f"{dates[1]}, "
            f"{dates[2]}"
        )

        st.write(
            f"**Time Slot:** "
            f"{time_slot}"
        )
