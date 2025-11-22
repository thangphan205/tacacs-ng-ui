import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { ProfileScriptSetPublic } from "@/client"
import DeleteProfileScriptSet from "../ProfileScriptSets/DeleteProfileScriptSet"
import EditProfileScriptSet from "../ProfileScriptSets/EditProfileScriptSet"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface ProfileScriptSetActionsMenuProps {
  profilescriptset: ProfileScriptSetPublic
}

export const ProfileScriptSetActionsMenu = ({ profilescriptset }: ProfileScriptSetActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditProfileScriptSet profilescriptset={profilescriptset} />
        <DeleteProfileScriptSet profilescriptset={profilescriptset} />
      </MenuContent>
    </MenuRoot>
  )
}
